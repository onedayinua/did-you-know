// content.js

function prefillPinData(data) {
  console.log("Extension received data:", data);

  // --- 1. SET TITLE ---
  // Look for the element with data-testid="pin-builder-draft-title"
  const titleInput = document.querySelector('[data-testid="pin-builder-draft-title"]');
  if (titleInput) {
    titleInput.value = data.title;
    // Trigger input event so Pinterest reacts to the change
    titleInput.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // --- 2. SET DESCRIPTION ---
  // Look for the editor element
  const descInput = document.querySelector('[data-testid="pin-builder-draft-description"] .public-DraftEditor-content');
  if (descInput) {
    // Draft.js is tricky. Simulating typing is best.
    descInput.focus();
    document.execCommand('insertText', false, data.description);
  }

  // --- 3. SET DESTINATION URL ---
  const urlInput = document.querySelector('[data-testid="pin-builder-draft-link"]');
  if (urlInput) {
    urlInput.value = data.url;
    urlInput.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // --- 4. HANDLE LOCAL IMAGE (The complex part) ---
  if (data.imageBase64) {
    uploadBase64Image(data.imageBase64);
  }
}

// Helper: Converts Base64 to a File object and simulates drag-and-drop
function uploadBase64Image(base64String) {
  const fileInput = document.querySelector('input[type="file"][id="media-upload-input"]');
  
  if (!fileInput) {
    console.error("Could not find Pinterest's image upload input.");
    return;
  }

  // Extract content type (e.g., image/jpeg) and raw base64 data
  const parts = base64String.split(';base64,');
  const contentType = parts[0].split(':')[1];
  const rawBase64 = parts[1];

  // Convert raw base64 to a Blob
  const byteCharacters = atob(rawBase64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  const blob = new Blob([byteArray], { type: contentType });

  // Create a File object from the Blob
  const file = new File([blob], "local_pin_image.jpg", { type: contentType });

  // Simulate a file drop event
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  
  fileInput.files = dataTransfer.files;
  
  // Trigger 'change' event to notify Pinterest's React handlers
  fileInput.dispatchEvent(new Event('change', { bubbles: true }));
}


// --- Message Listener ---
// Wait for the dashboard to send a message to this tab
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "prefill") {
    // Wait slightly to ensure the DOM is actually fully interactive
    setTimeout(() => {
        prefillPinData(request.data);
    }, 1500);
    sendResponse({status: "success"});
  }
});

console.log("Pinterest Pre-filler content script loaded.");