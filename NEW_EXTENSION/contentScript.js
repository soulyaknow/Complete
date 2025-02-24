console.log("Content script loaded.");

document.getElementById("sendData").addEventListener("click", async () => {
  const loginUrl = document.getElementById("loginUrl").value;
  // const username = document.getElementById("username").value;
  // const password = document.getElementById("password").value;

  // Save the loginUrl, username, and password to Chrome storage
  chrome.storage.local.set({ loginUrl }, () => {
    console.log("Data saved to Chrome storage.");
  });
});

chrome.storage.local.get(["loginUrl"], (data) => {
  const { loginUrl } = data;

  if (loginUrl) {
    document.getElementById("loginUrl").value = loginUrl;
    // document.getElementById("username").value = username;
    // document.getElementById("password").value = password;

    console.log("Form auto-filled with stored data.");

    chrome.storage.local.get("currentUrl", (targetData) => {
      const targetUrl = targetData.currentUrl;
      if (targetUrl) {
        document.getElementById("targetUrl").value = targetUrl;
        console.log("Target URL filled with saved data:", targetUrl);

        // Check if all fields are filled
        if (loginUrl && targetUrl) {
          console.log("All fields are filled. Auto-submitting the form...");

          // Trigger the click event programmatically
          document.getElementById("sendData").click();
        }
      } else {
        console.log("No target URL found in storage.");
      }
    });
  } else {
    console.log(
      "No stored data found, waiting for first-time form submission."
    );
  }
});
