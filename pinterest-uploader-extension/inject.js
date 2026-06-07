/**
 * Call this function from your dashboard button click
 * @param {string} title 
 * @param {string} description 
 * @param {string} destinationUrl - The final blog link
 * @param {string} imageBase64 - The FULL base64 data url, e.g., "data:image/jpeg;base64,/9j/4AAQ..."
 */
function sendPinToExtension(title, description, destinationUrl, imageBase64) {
    // 1. Defined the Extension ID (Find this on chrome://extensions page after loading)
    const EXTENSION_ID = "PASTE_YOUR_EXTENSION_ID_HERE";

    const payload = {
        title: title,
        description: description,
        url: destinationUrl,
        imageBase64: imageBase64 // Must include the data:image header
    };

    // 2. Contact the background script of the extension
    chrome.runtime.sendMessage(EXTENSION_ID, { 
        action: "openAndPrefill", 
        data: payload 
    }, (response) => {
        if (chrome.runtime.lastError) {
            console.error("Error connecting to extension:", chrome.runtime.lastError.message);
            alert("Ensure the extension is loaded and you pasted the correct ID in the dashboard code.");
        } else {
            console.log("Extension response:", response);
        }
    });
}