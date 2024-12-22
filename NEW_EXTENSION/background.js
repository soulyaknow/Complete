chrome.action.onClicked.addListener(async (tab) => {
  try {
    const [activeTab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    const currentUrl = activeTab.url;

    // Save the current URL to storage
    await chrome.storage.local.set({ currentUrl });

    const localWebsiteUrl = "http://localhost:2499"; // Your local website URL
    chrome.tabs.create({ url: localWebsiteUrl });

    // Inject the content script to handle pre-filling
    chrome.scripting.executeScript({
      target: { tabId: activeTab.id },
      files: ["contentScript.js"], // Content script for the web page
    });
  } catch (error) {
    console.error("Error handling extension click:", error);
  }
});

// Listen for messages from the content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { loginUrl, username, password } = message;

  if (loginUrl && username && password) {
    chrome.storage.local.set({ loginUrl, username, password }, () => {
      console.log("Data saved to Chrome storage:", message);
      sendResponse({ status: "success" });
    });
  } else {
    console.error("Invalid message data:", message);
    sendResponse({ status: "error", message: "Invalid data" });
  }

  return true; // Required to use `sendResponse` asynchronously
});
