const express = require("express");
const multer = require("multer");
const AWS = require("aws-sdk");
const axios = require("axios");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");
const mammoth = require("mammoth");
const xlsx = require("xlsx");
require("dotenv").config();
const { Pool } = require("pg");

const app = express();
const port = 3012;

// Configure AWS Textract
AWS.config.update({
  region: "ap-southeast-2",
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

const pool = new Pool({
  user: process.env.DB_USER,
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  password: process.env.DB_PASSWORD,
  port: process.env.DB_PORT,
});

pool
  .connect()
  .then(() => console.log("✅ Connected to PostgreSQL"))
  .catch((err) => console.error("❌ Database connection error:", err));

const textract = new AWS.Textract();
const s3 = new AWS.S3();
const n8nWebhookUrl = process.env.N8N_WEBHOOK_URL;
const awsBucketName = process.env.AWS_BUCKET_NAME;
const n8nExpenditureUrl = process.env.N8N_EXPENDITURE_URL;

// Configure multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage: storage });
const bucketName = awsBucketName;

const classifiedDocuments = {
  drivers_license: ["license", "id", "driver"],
  national_id: ["passport", "national", "citizen", "citizenship", "residency"],
  utility_bill: ["bill", "utility"],
  bank_statement: ["bank", "statement"],
  application_form: ["application", "form"],
  payslip: ["payslip", "salary", "payroll"],
  insurance: ["insurance", "policy", "coverage", "premium"],
};

const getDocumentType = (fileName) => {
  let normalizedFileName = fileName.toLowerCase().replace(/[^a-z0-9]/g, " ");
  for (let docType in classifiedDocuments) {
    if (
      classifiedDocuments[docType].some((keyword) =>
        new RegExp(`\\b${keyword}\\b`).test(normalizedFileName)
      )
    ) {
      return docType;
    }
  }
  return "unknown_document";
};

// Function to get Textract job results
const extractKeyValuePairs = (blocks) => {
  let keyMap = {};
  let valueMap = {};
  let keyValuePairs = {};

  // Step 1: Categorize blocks into keys and values
  blocks.forEach((block) => {
    if (
      block.BlockType === "KEY_VALUE_SET" &&
      block.EntityTypes.includes("KEY")
    ) {
      keyMap[block.Id] = block;
    } else if (
      block.BlockType === "KEY_VALUE_SET" &&
      block.EntityTypes.includes("VALUE")
    ) {
      valueMap[block.Id] = block;
    }
  });

  // Step 2: Match keys to values
  Object.values(keyMap).forEach((keyBlock) => {
    let keyText = getTextForBlock(keyBlock, blocks);
    let valueBlockId = keyBlock.Relationships?.find((r) => r.Type === "VALUE")
      ?.Ids?.[0];

    if (valueBlockId) {
      let valueText = getTextForBlock(valueMap[valueBlockId], blocks);
      keyValuePairs[keyText] = valueText;
    }
  });

  return keyValuePairs;
};

// Extracts text from block relationships
const getTextForBlock = (block, blocks) => {
  if (!block || !block.Relationships) return "";

  let text = "";
  block.Relationships.forEach((rel) => {
    if (rel.Type === "CHILD") {
      rel.Ids.forEach((childId) => {
        let wordBlock = blocks.find((b) => b.Id === childId);
        if (wordBlock && wordBlock.BlockType === "WORD") {
          text += wordBlock.Text + " ";
        }
      });
    }
  });

  return text.trim();
};

// Fetch Textract results and filter based on document type
const getTextractResults = async (jobId, documentType) => {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const jobResponse = await textract
          .getDocumentAnalysis({ JobId: jobId })
          .promise();

        if (jobResponse.JobStatus === "SUCCEEDED") {
          clearInterval(interval);

          let allBlocks = [];
          let nextToken = null;

          do {
            const pageResponse = await textract
              .getDocumentAnalysis({ JobId: jobId, NextToken: nextToken })
              .promise();

            allBlocks.push(...pageResponse.Blocks);
            nextToken = pageResponse.NextToken || null;
          } while (nextToken);

          // Extract structured form data
          const formResults = extractKeyValuePairs(allBlocks);

          // Extract table data
          const tableResults = extractTables(allBlocks);

          if (documentType) {
            resolve({ tableResults });
          } else {
            resolve({ formResults });
          }

          // resolve({ formResults, tableResults });
        } else if (jobResponse.JobStatus === "FAILED") {
          clearInterval(interval);
          reject("Textract job failed.");
        }
      } catch (error) {
        clearInterval(interval);
        reject(error);
      }
    }, 10000);
  });
};

const extractTables = (blocks) => {
  const tables = [];
  let currentTable = null;

  blocks.forEach((block) => {
    if (block.BlockType === "TABLE") {
      if (currentTable) tables.push(currentTable);
      currentTable = { rows: [] }; // Start new table
    }

    if (currentTable && block.BlockType === "CELL") {
      const cell = {
        rowIndex: block.RowIndex,
        columnIndex: block.ColumnIndex,
        text: getTextForBlock(block, blocks),
      };
      currentTable.rows.push(cell);
    }
  });

  if (currentTable) tables.push(currentTable); // Add last table
  return tables;
};

const convertToPDF = async (inputPath) => {
  const ext = path.extname(inputPath).toLowerCase();
  const outputPath = inputPath.replace(/\.\w+$/, ".pdf");

  try {
    if (ext === ".docx") {
      const { value } = await mammoth.convertToHtml({ path: inputPath });
      await generatePDF(value, outputPath);
    } else if (ext === ".xlsx") {
      const workbook = xlsx.readFile(inputPath);
      const sheetNames = workbook.SheetNames;
      const data = xlsx.utils.sheet_to_json(workbook.Sheets[sheetNames[0]]);
      const text = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
      await generatePDF(text, outputPath);
    } else if (ext === ".txt") {
      const text = fs.readFileSync(inputPath, "utf8");
      await generatePDF(`<pre>${text}</pre>`, outputPath);
    } else {
      return null; // Unsupported format
    }

    console.log(`Converted ${inputPath} to ${outputPath}`);

    // ✅ **Delete the original file after conversion**
    fs.unlinkSync(inputPath);
    console.log(`Deleted original file: ${inputPath}`);

    return outputPath;
  } catch (error) {
    console.error("Error converting file to PDF:", error);
    return null;
  }
};

const generatePDF = async (htmlContent, outputPath) => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setContent(`<html><body>${htmlContent}</body></html>`);
  await page.pdf({ path: outputPath, format: "A4" });
  await browser.close();
};

const sendToN8N = async (data) => {
  try {
    const response = await axios.post(n8nWebhookUrl, data, {
      headers: { "Content-Type": "application/json" },
    });
    console.log("✅ Successfully sent to n8n:", response.message);
  } catch (error) {
    console.error(
      "❌ Error sending to n8n:",
      error.response?.data || error.message
    );
  }
};

const sendToExpenditure = async (classifyData, applicants) => {
  const client = await pool.connect();
  try {
    // ✅ Handle multiple applicants correctly
    let applicantIdsArray, recordIdsArray;

    if (Array.isArray(applicants)) {
      // If multiple applicants, extract IDs and record IDs as an array
      applicantIdsArray = applicants.map((applicant) => applicant.applicant_id);
      recordIdsArray = applicants.map((applicant) => applicant.record_id);
    } else {
      // If single applicant, wrap in an array
      applicantIdsArray = [applicants.applicant_id];
      recordIdsArray = [applicants.record_id];
    }

    // ✅ Format headers correctly
    const formattedHeaders = {
      "Content-Type": "application/json",
      applicant_id:
        applicantIdsArray.length > 1
          ? JSON.stringify(applicantIdsArray)
          : applicantIdsArray[0],
      record_id:
        recordIdsArray.length > 1
          ? JSON.stringify(recordIdsArray)
          : recordIdsArray[0],
    };

    // ✅ Send data to n8n
    const response = await axios.post(n8nExpenditureUrl, classifyData, {
      headers: formattedHeaders,
    });

    console.log("✅ Successfully sent to n8n:", response.data);
  } catch (error) {
    console.error(
      "❌ Error sending to n8n:",
      error.response?.data || error.message
    );
  } finally {
    client.release();
  }
};

const saveDataToDB = async (applicantsData) => {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    // Create applicants table if it doesn't exist
    await client.query(`
      CREATE TABLE IF NOT EXISTS applicants (
        id SERIAL PRIMARY KEY,
        applicant_id INT NOT NULL,
        record_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    // Create extracted_data table if it doesn't exist
    await client.query(`
      CREATE TABLE IF NOT EXISTS extracted_data (
        id SERIAL PRIMARY KEY,
        applicant_id INT REFERENCES applicants(id) ON DELETE CASCADE,
        text TEXT,
        description TEXT,
        debit TEXT,
        credit TEXT,
        balance TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `);

    // Iterate over applicantsData
    console.log(applicantsData);
    for (const applicant of applicantsData) {
      const { applicant_id, record_id, full_name, extractedData } = applicant;

      // Validate required fields
      if (!applicant_id || !record_id || !full_name || !extractedData) {
        console.error("❌ Missing required applicant data", applicant);
        continue;
      }

      // Check if applicant exists
      const existingApplicant = await client.query(
        "SELECT id FROM applicants WHERE applicant_id = $1",
        [applicant_id]
      );

      let applicantId;
      if (existingApplicant.rows.length > 0) {
        applicantId = existingApplicant.rows[0].id;
      } else {
        // Insert new applicant
        const result = await client.query(
          "INSERT INTO applicants (applicant_id, record_id, full_name, created_at) VALUES ($1, $2, $3, NOW()) RETURNING id",
          [applicant_id, record_id, full_name]
        );
        applicantId = result.rows[0].id;
      }

      // Ensure extractedData.tableResults is an array before processing
      if (extractedData && Array.isArray(extractedData.tableResults)) {
        const tableResults = extractedData.tableResults;

        for (const dataItem of tableResults) {
          const rows = dataItem.rows;

          if (rows && rows.length > 0) {
            console.log("Processing rows:", rows);

            // Group rows by rowIndex
            const groupedRows = {};

            for (const row of rows) {
              const { rowIndex, columnIndex, text } = row;

              if (
                rowIndex === undefined ||
                columnIndex === undefined ||
                text === undefined
              ) {
                console.warn(
                  "❌ Missing required fields (rowIndex, columnIndex, text):",
                  row
                );
                continue;
              }

              if (!groupedRows[rowIndex]) {
                groupedRows[rowIndex] = { text: [] };
              }

              groupedRows[rowIndex].text[columnIndex - 1] = text;
            }

            // Convert groupedRows to database entries
            const dbEntries = [];
            for (const rowIndex in groupedRows) {
              const groupedRow = groupedRows[rowIndex];

              const rowData = {
                applicant_id: applicantId,
                text: groupedRow.text[0] || null,
                description: groupedRow.text[1] || null,
                debit: groupedRow.text[2] || null,
                credit: groupedRow.text[3] || null,
                balance: groupedRow.text[4] || null,
                created_at: new Date().toISOString(),
              };

              dbEntries.push(rowData);
            }

            // Insert all entries into extracted_data table
            for (const entry of dbEntries) {
              await client.query(
                "INSERT INTO extracted_data (applicant_id, text, description, debit, credit, balance, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                [
                  entry.applicant_id,
                  entry.text,
                  entry.description,
                  entry.debit,
                  entry.credit,
                  entry.balance,
                  entry.created_at,
                ]
              );
            }
          } else {
            console.error("❌ No rows found for this dataItem:", dataItem);
          }
        }
      } else {
        console.error(
          "❌ extractedData.tableResults is not an array or is undefined"
        );
      }

      console.log("✅ Processed applicant:", applicant);
    }

    await client.query("COMMIT");
    console.log("✅ Data saved to PostgreSQL");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("❌ Error saving to PostgreSQL:", err);
  } finally {
    client.release();
  }
};

const classification = async (applicantData) => {
  const client = await pool.connect();
  console.log("Received Applicant Data:", applicantData);

  try {
    // Use applicantData directly instead of parsing
    const applicants = applicantData;

    // Extract Applicant IDs
    const applicantIds = Object.keys(applicants).map((key) => {
      return {
        name: key,
        applicant_id: applicants[key].Applicant_ID,
        record_id: applicants[key].recordId,
      };
    });

    console.log("Extracted Applicant IDs:", applicantIds);

    // Iterate through all applicants and fetch details
    for (const applicant of applicantIds) {
      const { name, applicant_id } = applicant;
      console.log(`🔍 Searching for Applicant_ID: ${applicant_id}`);

      const applicantRes = await client.query(
        `SELECT id FROM applicants WHERE applicant_id = $1`,
        [applicant_id]
      );

      if (applicantRes.rows.length === 0) {
        console.warn(
          `⚠️ No matching applicant found for Applicant_ID: ${applicant_id}`
        );
        continue;
      }

      const applicantDbId = applicantRes.rows[0].id;
      console.log(`✅ Applicant '${name}' found with DB ID: ${applicantDbId}`);

      const extractedDataRes = await client.query(
        `SELECT id, description, debit, credit
         FROM extracted_data
         WHERE applicant_id = $1
         AND (debit ~ '^[0-9]' OR credit ~ '^[0-9]')
         AND description IS NOT NULL
         AND description <> ''`,
        [applicantDbId]
      );

      sendToExpenditure(extractedDataRes.rows, applicantIds);
    }
  } catch (error) {
    console.error("❌ Error querying database:", error);
  } finally {
    client.release();
  }
};

// POST endpoint to accept a file
app.post("/upload", upload.array("files", 10), async (req, res) => {
  if (!req.files || req.files.length === 0) {
    return res.status(400).send("No files uploaded.");
  }

  console.log(req.body);

  let jobResults = [];
  let nonBankStatementFiles = [];
  const bankStatements = [];
  const applicants = JSON.parse(req.body.applicants || "{}");

  try {
    for (const file of req.files) {
      const uploadDir = path.join(__dirname, "uploads");
      if (!fs.existsSync(uploadDir)) {
        fs.mkdirSync(uploadDir, { recursive: true });
      }

      let filePath = path.join(__dirname, "uploads", file.originalname);
      fs.writeFileSync(filePath, file.buffer);

      const fileExt = path.extname(file.originalname).toLowerCase();
      if (![".pdf", ".png", ".jpeg", ".jpg", ".tiff"].includes(fileExt)) {
        console.log(`Converting ${file.originalname} to PDF...`);
        const convertedPath = await convertToPDF(filePath);
        if (!convertedPath) {
          return res.status(400).send({ message: "Unsupported file type." });
        }
        filePath = convertedPath;
      }

      const s3Key = `uploads/${path.basename(filePath)}`;
      const fileBuffer = fs.readFileSync(filePath);
      const docType = getDocumentType(file.originalname);

      await s3
        .upload({
          Bucket: bucketName,
          Key: s3Key,
          Body: fileBuffer,
          ContentType: "application/pdf",
        })
        .promise();

      let textractResults;

      console.log("Document Type:", docType);

      if (docType === "bank_statement") {
        const startExtraction = await textract
          .startDocumentAnalysis({
            DocumentLocation: { S3Object: { Bucket: bucketName, Name: s3Key } },
            FeatureTypes: ["TABLES"],
          })
          .promise();

        const extractedId = startExtraction.JobId;
        console.log(`Started Textract job for ${file.originalname}`);
        textractResults = await getTextractResults(extractedId, true);

        const tableResults = textractResults && textractResults.tableResults;
        if (!Array.isArray(tableResults)) {
          console.error(
            "❌ No valid tableResults found for",
            file.originalname
          );
          textractResults = [];
        }

        bankStatements.push({
          file: file.originalname,
          classified: docType,
          message: `File processed successfully.`,
          extractedData: textractResults,
        });

        // 🔹 Assign bank statements to applicants
        const formattedData = [];
        const applicantKeys = Object.keys(applicants);

        if (bankStatements.length > 0) {
          for (let i = 0; i < bankStatements.length; i++) {
            const applicantKey = applicantKeys[i] || applicantKeys[0];
            const applicantData = applicants[applicantKey];
            const fullName = `${applicantData["First Name"]} ${applicantData["Last Name"]}`;

            formattedData.push({
              applicant_id: applicantData.Applicant_ID,
              record_id: applicantData.recordId,
              full_name: fullName,
              extractedData: bankStatements[i].extractedData,
            });
          }

          await saveDataToDB(formattedData);
          await classification(applicants);
        }
      } else {
        console.log(`Skipping non-bank statement file: ${file.originalname}`);
        const startResponse = await textract
          .startDocumentAnalysis({
            DocumentLocation: { S3Object: { Bucket: bucketName, Name: s3Key } },
            FeatureTypes: ["TABLES", "FORMS"],
          })
          .promise();

        const jobId = startResponse.JobId;
        console.log(`Started Textract job for ${file.originalname}`);
        textractResults = await getTextractResults(jobId, false);
        nonBankStatementFiles.push({
          file: file.originalname,
          classified: docType,
          message: `File processed successfully.`,
          extractedData: textractResults || [],
        });
      }

      // Delete uploaded file to save storage
      fs.unlinkSync(filePath);
    }

    // If there are non-bank statement files, send them to n8n
    if (nonBankStatementFiles.length > 0) {
      const applicant_data = {
        applicants: req.body.applicants || [],
        extract_data: nonBankStatementFiles,
      };

      sendToN8N(applicant_data);
    }

    res.status(200).send({
      message: "All files processed successfully.",
      results: {
        jobResults,
        nonBankStatementFiles,
        bankStatements,
      },
    });
  } catch (error) {
    console.error("Error processing files:", error);
    res.status(500).send("Error processing files.");
  }
});

app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});
