// background.js — Service Worker
//
// Handles external messages from the dashboard (via inject.js / chrome.runtime.sendMessage)
// and forwards them to the content script on a Pinterest pin-creation-tool tab.
//
// Flow:
//   1. Dashboard calls chrome.runtime.sendMessage(EXTENSION_ID, { action: "openAndPrefill", data: {...} })
//   2. This service worker receives it via chrome.runtime.onMessageExternal
//   3. Opens (or reuses) a Pinterest pin-creation-tool tab
//   4. Waits for the page to load, then sends a "prefill" message to that tab's content script

const PINTEREST_CREATION_URL = "https://www.pinterest.com/pin-creation-tool/";

chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  if (request.action === "openAndPrefill") {
    handleOpenAndPrefill(request.data)
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ status: "error", message: err.message }));
    return true; // Keep channel open for async response
  }
});

async function handleOpenAndPrefill(data) {
  // 1. Find or open a Pinterest creation tab
  let tab = await findOrCreatePinterestTab();

  // 2. Wait for the page to load
  await waitForTabComplete(tab.id);

  // 3. Send the prefill data to the content script
  const response = await chrome.tabs.sendMessage(tab.id, {
    action: "prefill",
    data: data,
  });

  return { status: "success", response: response };
}

async function findOrCreatePinterestTab() {
  // Look for an existing pin-creation-tool tab
  const tabs = await chrome.tabs.query({
    url: "*://*.pinterest.com/pin-creation-tool/*",
  });

  if (tabs.length > 0) {
    // Reuse the first matching tab
    await chrome.tabs.update(tabs[0].id, { active: true });
    return tabs[0];
  }

  // Open a new tab
  return await chrome.tabs.create({
    url: PINTEREST_CREATION_URL,
    active: true,
  });
}

function waitForTabComplete(tabId) {
  return new Promise((resolve) => {
    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        // Extra delay to ensure React/Draft.js is fully initialized
        setTimeout(resolve, 2000);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}