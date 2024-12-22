document.addEventListener("DOMContentLoaded", function () {
  const loginUrlField = document.getElementById("loginUrl");
  const usernameField = document.getElementById("username");
  const passwordField = document.getElementById("password");
  const targetUrlField = document.getElementById("targetUrl");
  const sendButton = document.getElementById("sendData");

  // Retrieve saved loginUrl, username, and password on extension load
  chrome.storage.local.get(["loginUrl", "username", "password"], (data) => {
    if (data.loginUrl) loginUrlField.value = data.loginUrl;
    if (data.username) usernameField.value = data.username;
    if (data.password) passwordField.value = data.password;
  });

  sendButton.addEventListener("click", function () {
    const loginUrl = loginUrlField.value;
    const username = usernameField.value;
    const password = passwordField.value;
    const targetUrl = targetUrlField.value;
 
    const seleniumEndpoint = "http://localhost:2500/process-url";

    const data = {
      loginUrl: loginUrl,
      targetUrl: targetUrl,
      username: username,
      password: password,
    };

    // Save only loginUrl, username, and password in Chrome storage
    chrome.storage.local.set({ loginUrl, username, password }, () => {
      console.log("Login credentials saved locally.");
    });

    // Show modal and disable button
    const modal = document.getElementById("modal");
    modal.style.display = "flex";
    sendButton.disabled = true;

    fetch(seleniumEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    })
      .then((response) => {
        if (response.ok) {
          return response.json();
        } else {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
      })
      .then((data) => {
        console.log("Data sent successfully:", data);
        alert("Data sent successfully!");
      })
      .catch((error) => {
        console.error("Error sending data:", error);
        alert("Failed to send data. Please try again.");
      })
      .finally(() => {
        // Hide modal and re-enable button
        modal.style.display = "none";
        sendButton.disabled = false;
      });
  });
});
