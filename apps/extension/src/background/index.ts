chrome.action.onClicked.addListener((tab) => {
  if (tab.id === undefined) return;
  void chrome.sidePanel.open({ tabId: tab.id }).catch((error: unknown) => {
    console.error('Could not open auto-fill side panel', error);
  });
});
