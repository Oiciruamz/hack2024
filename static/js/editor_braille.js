/**
 * Editor de revisión OCR y Braille - Lectura Abierta / Letras Inclusivas
 * Gestiona edición por bloques, sincronización braille con debounce,
 * cancelación de respuestas obsoletas, guardado automático y paginación.
 */

(function () {
  'use strict';

  // Configuración y estado inicial proveniente del template HTML
  const config = window.__BRAILLE_EDITOR_CONFIG__ || {};
  const reviewId = config.reviewId || '';
  const pages = config.pages || [{ page_number: 1, text: '', original_text: '' }];
  let currentPageIndex = 0;

  // Variables de control de concurrencia y timers
  let currentSeq = 0;
  let lastAcceptedSeq = 0;
  let translateTimer = null;
  let saveTimer = null;
  let isSaving = false;

  // Elementos del DOM
  const ocrText = document.getElementById('ocrText');
  const braillePreview = document.getElementById('braillePreview');
  const wordCount = document.getElementById('wordCount');
  const charCount = document.getElementById('charCount');
  const saveStatus = document.getElementById('saveStatus');
  const saveDot = document.getElementById('saveDot');
  const brailleStatus = document.getElementById('brailleStatus');
  const prevPageBtn = document.getElementById('prevPageBtn');
  const nextPageBtn = document.getElementById('nextPageBtn');
  const pageIndicator = document.getElementById('pageIndicator');
  const btnRestaurar = document.getElementById('btnRestaurar');
  const btnFinalizar = document.getElementById('btnFinalizar');
  const finalizeForm = document.getElementById('finalizeForm');
  const formPageText = document.getElementById('formPageText');
  const formPageIndex = document.getElementById('formPageIndex');
  const retryBrailleBtn = document.getElementById('retryBrailleBtn');

  function updateCounters(text) {
    const trimmed = (text || '').trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const chars = (text || '').length;
    if (wordCount) wordCount.textContent = `${words} palabra${words === 1 ? '' : 's'}`;
    if (charCount) charCount.textContent = `${chars} caracter${chars === 1 ? '' : 'es'}`;
  }

  function setSaveState(state, message) {
    if (!saveStatus) return;
    saveStatus.textContent = message;
    if (saveDot) {
      saveDot.className = 'eb-dot' + (state === 'saving' ? ' saving' : state === 'error' ? ' error' : '');
    }
  }

  function setBrailleState(state, message) {
    if (!brailleStatus) return;
    brailleStatus.textContent = message;
    if (retryBrailleBtn) {
      retryBrailleBtn.style.display = state === 'error' ? 'inline-flex' : 'none';
    }
  }

  // Traducción en tiempo real con debounce y token de secuencia
  function requestBrailleTranslation(text) {
    setBrailleState('loading', 'Actualizando braille…');
    clearTimeout(translateTimer);

    translateTimer = setTimeout(async () => {
      const seq = ++currentSeq;

      try {
        const response = await fetch('/api/traducir-braille', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({ text: text, seq: seq }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Evitar condiciones de carrera: descartar respuestas antiguas si hubo una edición posterior
        if (data.seq >= lastAcceptedSeq) {
          lastAcceptedSeq = data.seq;
          if (braillePreview) {
            braillePreview.textContent = data.braille || '⠿';
          }
          setBrailleState('ready', 'Al día');
        }
      } catch (err) {
        console.error('Error al traducir a braille:', err);
        setBrailleState('error', 'Error al traducir');
      }
    }, 350);
  }

  // Guardado automático debounced
  function scheduleAutosave() {
    setSaveState('saving', 'Guardando cambios…');
    clearTimeout(saveTimer);

    saveTimer = setTimeout(() => {
      saveCurrentPageToServer();
    }, 800);
  }

  async function saveCurrentPageToServer() {
    if (!reviewId || isSaving) return;
    isSaving = true;

    const textToSave = ocrText ? ocrText.value : '';
    if (pages[currentPageIndex]) {
      pages[currentPageIndex].text = textToSave;
    }

    try {
      const response = await fetch(`/api/guardar-revision/${reviewId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          page_index: currentPageIndex,
          text: textToSave,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      setSaveState('saved', 'Cambios guardados');
    } catch (err) {
      console.error('Error al autoguardar página:', err);
      setSaveState('error', 'Error al guardar');
    } finally {
      isSaving = false;
    }
  }

  // Cambio de página para documentos con múltiples páginas
  function loadPage(pageIndex) {
    if (pageIndex < 0 || pageIndex >= pages.length) return;

    // Guardar cambios de la página actual antes de cambiar
    if (ocrText && pages[currentPageIndex]) {
      pages[currentPageIndex].text = ocrText.value;
    }
    saveCurrentPageToServer();

    currentPageIndex = pageIndex;
    const cur = pages[currentPageIndex] || { text: '' };

    if (ocrText) {
      ocrText.value = cur.text || '';
    }

    updateCounters(cur.text || '');
    updatePaginationUI();
    requestBrailleTranslation(cur.text || '');
  }

  function updatePaginationUI() {
    if (pageIndicator) {
      pageIndicator.textContent = `Página ${currentPageIndex + 1} de ${pages.length}`;
    }
    if (prevPageBtn) {
      prevPageBtn.disabled = currentPageIndex <= 0;
    }
    if (nextPageBtn) {
      nextPageBtn.disabled = currentPageIndex >= pages.length - 1;
    }
  }

  // Restaurar texto OCR original
  async function restaurarOcrActual() {
    if (!confirm('¿Deseas restaurar el texto OCR original de esta página? Se perderán las correcciones manuales realizadas en ella.')) {
      return;
    }

    try {
      setSaveState('saving', 'Restaurando OCR…');
      const response = await fetch(`/api/restaurar-ocr/${reviewId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({ page_index: currentPageIndex }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      if (ocrText) {
        ocrText.value = data.text;
      }
      if (pages[currentPageIndex]) {
        pages[currentPageIndex].text = data.text;
      }

      updateCounters(data.text);
      if (braillePreview) {
        braillePreview.textContent = data.braille || '⠿';
      }
      setSaveState('saved', 'OCR restaurado');
      setBrailleState('ready', 'Al día');
    } catch (err) {
      console.error('Error al restaurar OCR:', err);
      setSaveState('error', 'Error al restaurar');
    }
  }

  // Inicialización de eventos
  if (ocrText) {
    ocrText.addEventListener('input', function () {
      const text = ocrText.value;
      if (pages[currentPageIndex]) {
        pages[currentPageIndex].text = text;
      }
      updateCounters(text);
      requestBrailleTranslation(text);
      scheduleAutosave();
    });
  }

  if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => loadPage(currentPageIndex - 1));
  }

  if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => loadPage(currentPageIndex + 1));
  }

  if (btnRestaurar) {
    btnRestaurar.addEventListener('click', restaurarOcrActual);
  }

  if (retryBrailleBtn) {
    retryBrailleBtn.addEventListener('click', () => {
      if (ocrText) requestBrailleTranslation(ocrText.value);
    });
  }

  if (btnFinalizar && finalizeForm) {
    btnFinalizar.addEventListener('click', async (e) => {
      e.preventDefault();
      btnFinalizar.disabled = true;
      btnFinalizar.textContent = 'Finalizando y generando archivos…';

      // Asegurar que el último texto esté sincronizado en el formulario
      if (formPageText && ocrText) {
        formPageText.value = ocrText.value;
      }
      if (formPageIndex) {
        formPageIndex.value = currentPageIndex;
      }

      // Guardar antes de enviar
      await saveCurrentPageToServer();
      finalizeForm.submit();
    });
  }

  // Inicialización al cargar la pantalla
  if (ocrText) {
    updateCounters(ocrText.value);
    updatePaginationUI();
  }
})();
