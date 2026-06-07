document.getElementById('save').addEventListener('click', () => {
  const boardUrl = document.getElementById('boardUrl').value;
  chrome.storage.sync.set({ defaultBoardUrl: boardUrl }, () => {
    alert('Settings saved!');
  });
});

// Restore settings when the page loads
chrome.storage.sync.get('defaultBoardUrl', (data) => {
  if (data.defaultBoardUrl) {
    document.getElementById('boardUrl').value = data.defaultBoardUrl;
  }
});