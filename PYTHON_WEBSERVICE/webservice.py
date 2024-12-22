from flask import Flask, request, jsonify, render_template_string
import requests
import subprocess
import os

# Initialize the Flask application
app = Flask(__name__)

# Configuration for the GitLab API
GITLAB_API_URL = "https://gitlab.com/api/v4/projects/YOUR_PROJECT_ID/repository/commits"
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")  # Securely stored token

latest_commit_hash = None

def check_for_updates():
    global latest_commit_hash
    try:
        response = requests.get(
            f"{GITLAB_API_URL}?ref_name=main",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        
        data = response.json()
        latest_commit = data[0].get("id")
        
        if not latest_commit_hash or latest_commit != latest_commit_hash:
            print("New update found, pulling changes...")
            latest_commit_hash = latest_commit
            subprocess.run(["git", "pull", "origin", "main"], check=True)
        else:
            print("No updates found, starting application normally.")
    except requests.exceptions.RequestException as e:
        print(f"Error checking for updates: {e}")
        print("Starting application normally...")

# Route to get application data
@app.route('/rpa/<record_id>', methods=['GET'])
def get_record_details(record_id):
    application_hub_api = f"https://ai-broker.korunaassist.com/fusion/v1/datasheets/dstLr3xUL37tbn2Sud/records?record_id={record_id}"
    broker_hub_api = f"https://ai-broker.korunaassist.com/fusion/v1/datasheets/dstuqAhBamoBAzziwt/records?record_id="

    try:
        # Fetch application hub data
        application_response = requests.get(
            application_hub_api,
            headers={
                "Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j",
                "Content-Type": "application/json",
            }
        )
        application_response.raise_for_status()
        application_data = application_response.json()

        if not application_data.get("data") or not application_data["data"].get("records"):
            return "<h1>Application record not found</h1>", 404

        application_record = next(
            (record for record in application_data["data"]["records"] if record["recordId"] == record_id),
            None
        )

        if not application_record:
            return "<h1>Application record not found</h1>", 404

        # Generate table rows with specific handling for nested fields
        data_rows = "".join(
            f"<tr><td>{key}</td><td>{format_field_value(key, value)}</td></tr>"
            for key, value in application_record["fields"].items()
        )

        # Fetch broker hub data
        broker_id = application_record["fields"]["Broker"][0]
        broker_response = requests.get(
            f"{broker_hub_api}{broker_id}",
            headers={
                "Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j",
                "Content-Type": "application/json",
            }
        )
        broker_response.raise_for_status()
        broker_data = broker_response.json()

        if not broker_data.get("data") or not broker_data["data"].get("records"):
            return "<h1>Broker record not found</h1>", 404

        broker_record = next(
            (record for record in broker_data["data"]["records"] if record["recordId"] == broker_id),
            None
        )

        if not broker_record:
            return "<h1>Broker record not found</h1>", 404

        broker_info = {
            "recordId": broker_record["recordId"],
            "thirdPartyAggregator": broker_record["fields"].get("3rd Party Aggregator"),
            "thirdPartyCRM": broker_record["fields"].get("3rd Party CRM"),
        }

        # Render the HTML response
        html_template = f"""
        <html>
        <head>
            <title>Record Details</title>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid black; padding: 10px; text-align: left; }}
                .dark-mode {{ background-color: #121212; color: #ffffff; }}
                .dark-mode table {{ border-color: #333; }}
                .dark-mode th, .dark-mode td {{ border-color: #333; }}
                button {{ margin: 10px; padding: 10px; }}
                .btn {{ margin: 10px; padding:10px; width: 10%; }}
                .modal-overlay {{
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 100;
                }}
                .modal {{
                    display: none;
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: white;
                    padding: 20px;
                    box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.5);
                    z-index: 101;
                }}
                .modal.show {{
                    display: block;
                }}
            </style>
        </head>
        <body>
            <button onclick="toggleDarkMode()">Toggle Dark Mode</button>
            <h1>Record Details for ID: {record_id}</h1>
            <table>
                <tr><th>Field</th><th>Value</th></tr>
                {data_rows}
            </table>
            <button onclick="showModal()" class="btn">Run</button>
            <!-- Modal Structure -->
            <div id="modal-overlay" class="modal-overlay"></div>
            <div id="modal" class="modal">
                <h2>Authentication</h2>
                <form id="auth-form">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                    <button type="button" onclick="submitCredentials()">Submit</button>
                </form>
            </div>
            <script>
                const applicationData = {application_record};
                const brokerData = {broker_info};
                function toggleDarkMode() {{
                    document.body.classList.toggle('dark-mode');
                }}
                function showModal() {{
                    document.getElementById('modal').classList.add('show');
                    document.getElementById('modal-overlay').style.display = 'block';
                }}

                function hideModal() {{
                    document.getElementById('modal').classList.remove('show');
                    document.getElementById('modal-overlay').style.display = 'none';
                }}

                function submitCredentials() {{
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;

                    if (username && password) {{
                        executeTagUI(username, password);
                        hideModal();
                    }} else {{
                        alert('Please enter both username and password.');
                    }}
                }}
                function executeTagUI(username, password) {{
                    fetch("http://localhost:5213/execute-selenium-script", {{
                        method: "POST",
                        headers: {{
                            "Content-Type": "application/json"
                        }},
                        body: JSON.stringify({{
                            applicationData: applicationData,
                            brokerData: brokerData,
                            username: username,
                            password: password
                        }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        console.log(data.success ? "TagUI script executed successfully!" : "Failed to execute TagUI script.");
                        console.log(data);
                    }})
                    .catch(error => console.error("Error executing TagUI script:", error));
                }}
            </script>
        </body>
        </html>
        """
        return render_template_string(html_template)
    except requests.exceptions.RequestException as e:
        return f"<h1>Error fetching data: {e}</h1>", 500

def format_field_value(key, value):
    if key in ["License", "Passport", "Fact Find"]:
        return (
            "".join(
                f"Name: {item['name']}<br /><br />Size: {item['size']} bytes<br /><br />MIME Type: {item['mimeType']}<br /><br />URL: {item['url']}<br />"
                for item in value
            )
            if isinstance(value, list)
            else value
        )
    elif key in ["dependents", "applicants", "broker", "loanType", "status"]:
        return ", ".join(item["name"] if isinstance(item, dict) else str(item) for item in value) if isinstance(value, list) else value
    else:
        return ", ".join(value) if isinstance(value, list) else value

if __name__ == "__main__":
    check_for_updates()  # Check for updates on server start
    app.run(debug=True, port=5123, host="0.0.0.0")
