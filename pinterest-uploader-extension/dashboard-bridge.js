// dashboard-bridge.js — Content script injected into the dashboard (localhost:8000)
//
// Bridges postMessage calls from the web page to the extension's background service worker.
// The web page cannot access chrome.runtime directly, so it uses window.postMessage instead.

console.log("[DashboardBridge] Content script loaded on dashboard page");

window.addEventListener("message", (event) => {
  // Only accept messages from the same window (not cross-origin iframes)
  if (event.source !== window) return;

  // Only handle our specific messages
  if (event.data && event.data.source === "did-you-know-dashboard") {
    const { action, data, requestId } = event.data;
    console.log("[DashboardBridge] Received postMessage:", { action, requestId });

    if (action === "openAndPrefill") {
      chrome.runtime.sendMessage(
        { action: "openAndPrefill", data: data },
        (response) => {
          console.log("[DashboardBridge] Background response:", response);
          // Send response back to the web page
          window.postMessage(
            {
              source: "did-you-know-extension",
              requestId: requestId,
              response: response,
            },
            window.location.origin
          );
        }
      );
    }
  }
});