(async function () {
  try {
    const config = window.BREE_DECK_CONFIG;
    let data;
    for (const address of [config.dataUrl, config.fallbackDataUrl]) {
      try {
        const url = new URL(address);
        url.searchParams.set('_deck', String(Date.now()));
        const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin'});
        if (!response.ok) throw new Error('Data request failed');
        data = await response.json();
        if (!Array.isArray(data.characters) || !data.characters.length) throw new Error('Empty Deck data');
        break;
      } catch (error) { data = null; }
    }
    if (!data) throw new Error('Data could not be loaded');
    window.DECK_CHARS = data;
    const script = document.createElement('script');
    script.src = config.scriptUrl;
    script.onerror = showError;
    document.body.appendChild(script);
  } catch (error) {
    showError();
  }
  function showError() {
    const message = document.getElementById('ascii-pre');
    if (message) message.textContent = 'The Character Deck could not be loaded. Please reload this page to try again.';
  }
})();
