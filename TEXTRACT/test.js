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

const connectWithRetry = (retries = 30, delay = 5000) => {
  pool
    .connect()
    .then(() => console.log("✅ Connected to PostgreSQL"))
    .catch((err) => {
      console.error("❌ Database connection error:", err);
      if (retries > 0) {
        console.log(
          `Retrying in ${delay / 1000}s... (${retries} attempts left)`
        );
        setTimeout(() => connectWithRetry(retries - 1, delay), delay);
      } else {
        console.error("❌ Failed to connect after multiple attempts.");
        process.exit(1);
      }
    });
};

const textract = new AWS.Textract();
const s3 = new AWS.S3();
const n8nWebhookUrl = process.env.N8N_WEBHOOK_URL;
const awsBucketName = process.env.AWS_BUCKET_NAME;
const n8nExpenditureUrl = process.env.N8N_EXPENDITURE_URL;

// Configure multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage: storage });
const bucketName = awsBucketName;

// Global variables to manage document processing queue
let processingQueue = [];
let isProcessing = false;
let n8nProcessing = false;

// Debug function to print current queue status
const printQueueStatus = () => {
  console.log("=== Queue Status ===");
  console.log(`isProcessing: ${isProcessing}`);
  console.log(`n8nProcessing: ${n8nProcessing}`);
  console.log(`Queue length: ${processingQueue.length}`);
  if (processingQueue.length > 0) {
    console.log("Files in queue:");
    processingQueue.forEach((item, index) => {
      console.log(`  ${index + 1}. ${item.file.originalname}`);
    });
  }
  console.log("====================");
};

const classifiedDocuments = {
  bank_statement: [
    "bank",
    "statement",
    "transaction",
    "account",
    "banking",
    "deposit",
    "withdrawal",
    "balance",
    "credit",
    "debit",
    "interest",
    "overdraft",
    "transfer",
    "statement period",
    "monthly statement",
    "checking",
    "savings",
    "financial summary",
    "ledger",
    "IBAN",
    "SWIFT",
    "sort code",
  ],
  drivers_license: ["license", "driver", "driving", "licence"],
  national_id: [
    "passport",
    "national",
    "id",
    "identification",
    "citizen",
    "citizenship",
    "residency",
  ],
  utility_bill: [
    "bill",
    "utility",
    "electric",
    "water",
    "gas",
    "electricity",
    "utilities",
  ],
  application_form: ["application", "form", "forms"],
  payslip: ["payslip", "salary", "wage", "payment", "payroll", "pay"],
  insurance: ["insurance", "policy", "coverage", "premium"],
};

// Check if n8n is currently processing
const checkN8nStatus = async () => {
  return n8nProcessing;
};

// Improve document type detection to handle numbers
const getDocumentType = (fileName) => {
  console.log("Analyzing document type for:", fileName);
  // Remove file extension and normalize
  const normalizedFileName = fileName
    .toLowerCase()
    .replace(/\.[^/.]+$/, "")
    .replace(/[^a-z0-9]/g, " ");

  for (const [docType, keywords] of Object.entries(classifiedDocuments)) {
    for (const keyword of keywords) {
      // Use a more flexible pattern that works with numbers
      if (normalizedFileName.includes(keyword)) {
        console.log(`Matched keyword "${keyword}" for type "${docType}"`);
        return docType;
      }
    }
  }

  console.log("No matching document type found, using unknown_document");
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
    n8nProcessing = true;
    console.log("Sending data to n8n...");
    const response = await axios.post(n8nWebhookUrl, data, {
      headers: { "Content-Type": "application/json" },
    });
    console.log("✅ Successfully sent to n8n:", response.data);

    // Important: Wait a moment before clearing the n8nProcessing flag
    // This ensures we don't start the next job too quickly
    setTimeout(() => {
      n8nProcessing = false;
      console.log("n8n processing flag cleared, ready for next document");
      processNextDocument();
    }, 1000);

    return response;
  } catch (error) {
    console.error(
      "❌ Error sending to n8n:",
      error.response?.data || error.message
    );
    n8nProcessing = false;

    // Even if there's an error, try to process the next document
    setTimeout(() => {
      processNextDocument();
    }, 1000);

    throw error;
  }
};

const sendToExpenditure = async (classifyData, applicants, extractedId) => {
  try {
    n8nProcessing = true;
    console.log("Sending data to expenditure endpoint...");

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
      extracted_bank_id: extractedId,
    };

    // ✅ Send data to n8n
    const response = await axios.post(n8nExpenditureUrl, classifyData, {
      headers: formattedHeaders,
    });

    console.log("✅ Successfully sent to n8n expenditure:", response.data);

    // Important: Wait a moment before clearing the n8nProcessing flag
    // This ensures we don't start the next job too quickly
    setTimeout(() => {
      n8nProcessing = false;
      console.log(
        "n8n expenditure processing flag cleared, ready for next document"
      );
      processNextDocument();
    }, 1000);

    return response;
  } catch (error) {
    console.error(
      "❌ Error sending to n8n expenditure:",
      error.response?.data || error.message
    );
    n8nProcessing = false;

    // Even if there's an error, try to process the next document
    setTimeout(() => {
      processNextDocument();
    }, 1000);

    throw error;
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

    // Add processed column if it doesn't exist
    await client.query(`
        DO $$ 
        BEGIN 
          IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'extracted_data' 
            AND column_name = 'processed'
          ) THEN 
            ALTER TABLE extracted_data 
            ADD COLUMN processed BOOLEAN DEFAULT false;
          END IF;
        END $$;
      `);

    let newlyInsertedIds = [];

    // Helper function to clean currency values
    const cleanCurrencyValue = (value) => {
      if (!value) return null;

      // Remove $ and DR, but keep commas and decimal points
      // This will result in formats like 80,000.00 or 82,994.30
      return value.replace(/[$DR\s]/g, "");
    };

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

              // Clean currency values before storing
              const rawDebit = groupedRow.text[2] || null;
              const rawCredit = groupedRow.text[3] || null;
              const rawBalance = groupedRow.text[4] || null;

              const rowData = {
                applicant_id: applicantId,
                text: groupedRow.text[0] || null,
                description: groupedRow.text[1] || null,
                debit: cleanCurrencyValue(rawDebit),
                credit: cleanCurrencyValue(rawCredit),
                balance: cleanCurrencyValue(rawBalance),
                created_at: new Date().toISOString(),
              };

              dbEntries.push(rowData);
            }

            // Insert all entries into extracted_data table and collect their IDs
            for (const entry of dbEntries) {
              const result = await client.query(
                "INSERT INTO extracted_data (applicant_id, text, description, debit, credit, balance, created_at, processed) VALUES ($1, $2, $3, $4, $5, $6, $7, false) RETURNING id",
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
              newlyInsertedIds.push(result.rows[0].id);
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

    // Process next document if available after a short delay
    setTimeout(() => {
      processNextDocument();
    }, 1000);

    return newlyInsertedIds; // Return the IDs of newly inserted records
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("❌ Error saving to PostgreSQL:", err);

    // Even if there's an error, try to process the next document after a short delay
    setTimeout(() => {
      processNextDocument();
    }, 1000);

    return [];
  } finally {
    client.release();
  }
};

const classification = async (extractedId, applicantData) => {
  const client = await pool.connect();
  try {
    const applicants = applicantData;

    // Extract Applicant IDs
    const applicantIds = Object.keys(applicants).map((key) => {
      return {
        name: key,
        applicant_id: applicants[key].Applicant_ID,
        record_id: applicants[key].recordId,
      };
    });

    const dataStructure = {};

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

      // Only get unprocessed records
      const extractedDataRes = await client.query(
        `SELECT id, text, description, debit, credit
         FROM extracted_data
         WHERE applicant_id = $1
         AND processed = false
         AND (debit ~ '^[0-9]' OR credit ~ '^[0-9]')
         AND description IS NOT NULL
         AND text IS NOT NULL
         AND description <> ''`,
        [applicantDbId]
      );

      if (extractedDataRes.rows.length > 0) {
        // Store results in the structured format
        dataStructure[`applicant_${applicant_id}`] = {
          applicant_name: name,
          applicant_id: applicant_id,
          extractData: {
            extractedRows: extractedDataRes.rows,
          },
        };

        // Mark these records as processed
        const ids = extractedDataRes.rows.map((row) => row.id);
        await client.query(
          `UPDATE extracted_data 
           SET processed = true 
           WHERE id = ANY($1)`,
          [ids]
        );

        // Log the final structured data
        console.log(
          "📂 Structured Data:",
          JSON.stringify(dataStructure, null, 2)
        );

        // Only send if we have new data
        await sendToExpenditure(
          extractedDataRes.rows,
          applicantIds,
          extractedId
        );
      } else {
        console.log(`No new data to process for applicant ${name}`);

        // Even if there's no new data, check if there are more documents to process
        setTimeout(() => {
          processNextDocument();
        }, 1000);
      }
    }
  } catch (error) {
    console.error("❌ Error querying database:", error);

    // Even if there's an error, try to process the next document
    setTimeout(() => {
      processNextDocument();
    }, 1000);
  } finally {
    client.release();
  }
};

// Process a single document from the queue
const processDocument = async (fileObj, applicants) => {
  // Safety check - if we're already processing, don't proceed
  if (isProcessing) {
    console.log(
      `Already processing another document, queuing ${fileObj.file.originalname}`
    );
    return;
  }

  // Set the flag to prevent concurrent processing
  isProcessing = true;

  console.log(`🔄 Processing document: ${fileObj.file.originalname}`);
  printQueueStatus();

  try {
    const uploadDir = path.join(__dirname, "uploads");
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }

    let filePath = path.join(__dirname, "uploads", fileObj.file.originalname);
    fs.writeFileSync(filePath, fileObj.file.buffer);

    const fileExt = path.extname(fileObj.file.originalname).toLowerCase();
    if (![".pdf", ".png", ".jpeg", ".jpg", ".tiff"].includes(fileExt)) {
      console.log(`Converting ${fileObj.file.originalname} to PDF...`);
      const convertedPath = await convertToPDF(filePath);
      if (!convertedPath) {
        throw new Error("Unsupported file type.");
      }
      filePath = convertedPath;
    }

    const s3Key = `uploads/${path.basename(filePath)}`;
    const fileBuffer = fs.readFileSync(filePath);

    // Get document type from filename
    const docType = getDocumentType(fileObj.file.originalname);
    console.log("Document Type:", docType);

    // Upload to S3
    await s3
      .upload({
        Bucket: bucketName,
        Key: s3Key,
        Body: fileBuffer,
        ContentType: "application/pdf",
      })
      .promise();

    let textractResults;

    if (docType === "bank_statement") {
      // Process bank statements
      const startExtraction = await textract
        .startDocumentAnalysis({
          DocumentLocation: { S3Object: { Bucket: bucketName, Name: s3Key } },
          FeatureTypes: ["TABLES"],
        })
        .promise();

      const extractedId = startExtraction.JobId;
      console.log(`Started Textract job for ${fileObj.file.originalname}`);
      textractResults = await getTextractResults(extractedId, true);

      const tableResults = textractResults && textractResults.tableResults;
      if (!Array.isArray(tableResults)) {
        console.error(
          "❌ No valid tableResults found for",
          fileObj.file.originalname
        );
        textractResults = { tableResults: [] };
      }

      const bankStatement = {
        file: fileObj.file.originalname,
        classified: docType,
        message: `File processed successfully.`,
        extractedData: textractResults,
      };

      // Process bank statement with applicant data
      const formattedData = [];
      const applicantKeys = Object.keys(applicants);
      const applicantKey = applicantKeys[0]; // Use first applicant for now
      const applicantData = applicants[applicantKey];

      if (applicantData) {
        formattedData.push({
          applicant_id: applicantData.Applicant_ID,
          record_id: applicantData.recordId,
          full_name: `${applicantData["First Name"]} ${applicantData["Last Name"]}`,
          extractedData: bankStatement.extractedData,
        });
      }

      // Save to DB and prepare for n8n
      await saveDataToDB(formattedData);
      await classification(extractedId, applicants);
    } else {
      // Process non-bank statement files
      console.log(
        `Processing non-bank statement file: ${fileObj.file.originalname}`
      );
      const startResponse = await textract
        .startDocumentAnalysis({
          DocumentLocation: { S3Object: { Bucket: bucketName, Name: s3Key } },
          FeatureTypes: ["TABLES", "FORMS"],
        })
        .promise();

      const jobId = startResponse.JobId;
      console.log(`Started Textract job for ${fileObj.file.originalname}`);
      textractResults = await getTextractResults(jobId, false);

      const nonBankFile = {
        file: fileObj.file.originalname,
        classified: docType,
        message: `File processed successfully.`,
        extractedData: textractResults || [],
      };

      // Process with n8n
      const applicant_data = {
        applicants: applicants,
        extract_data: [nonBankFile],
      };

      await sendToN8N(applicant_data);
    }

    // Clean up: Delete uploaded file to save storage
    fs.unlinkSync(filePath);

    console.log(`✅ Successfully processed ${fileObj.file.originalname}`);
  } catch (error) {
    console.error(
      `❌ Error processing document ${fileObj.file.originalname}:`,
      error
    );

    // Release the processing lock and trigger next document processing
    isProcessing = false;
    setTimeout(() => {
      processNextDocument();
    }, 1000);
  } finally {
    // Release the processing lock
    isProcessing = false;

    // Check if more documents are in the queue
    console.log(
      `Processing of ${fileObj.file.originalname} complete, checking for more documents...`
    );
    processNextDocument();
  }
};

// Start processing the next document in the queue if not currently processing
const processNextDocument = async () => {
  // First, print queue status for debugging
  printQueueStatus();

  // If already processing a document, don't start another one
  if (isProcessing) {
    console.log("Already processing a document, will check again later");
    return;
  }

  // If n8n is processing, wait before processing next document
  if (n8nProcessing) {
    console.log(
      "n8n is currently processing, waiting before starting next document"
    );
    setTimeout(processNextDocument, 2000); // Check again after 2 seconds
    return;
  }

  // If queue has documents, process the next one
  if (processingQueue.length > 0) {
    const nextDoc = processingQueue.shift();
    console.log(
      `Starting processing for next document: ${nextDoc.file.originalname}`
    );
    await processDocument(nextDoc, nextDoc.applicants);
  } else {
    console.log("No more documents in the processing queue");
  }
};

// Upload endpoint - modified to handle sequential processing
app.post("/upload", upload.array("files", 10), async (req, res) => {
  if (!req.files || req.files.length === 0) {
    return res.status(400).send("No files uploaded.");
  }

  console.log(`Received ${req.files.length} files for processing`);

  // Parse applicant data - handle both singular and plural forms
  let applicants = {};
  if (req.body.applicant) {
    // Handle single applicant case
    const applicantData = JSON.parse(req.body.applicant);
    applicants = {
      Applicant1: applicantData,
    };
  } else if (req.body.applicants) {
    // Handle multiple applicants case
    applicants = JSON.parse(req.body.applicants || "{}");
  }

  try {
    // Add files to the processing queue
    for (const file of req.files) {
      processingQueue.push({
        file,
        applicants,
      });
      console.log(`Added ${file.originalname} to processing queue`);
    }

    // Print queue status after adding files
    printQueueStatus();

    // Start processing the first document immediately if not already processing
    if (!isProcessing && !n8nProcessing) {
      processNextDocument();
    } else {
      console.log(
        "A document is already processing. New files have been queued."
      );
    }

    // Respond immediately that files have been queued
    res.status(200).send({
      message: "All files have been queued for processing.",
      queueStatus: {
        totalFiles: req.files.length,
        processing: isProcessing,
        remainingInQueue: processingQueue.length,
      },
    });
  } catch (error) {
    console.error("Error queueing files:", error);
    res.status(500).send("Error queueing files for processing.");
  }
});

app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
  connectWithRetry();
});
