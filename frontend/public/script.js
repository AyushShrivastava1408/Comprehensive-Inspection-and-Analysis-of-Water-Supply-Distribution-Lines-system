/* AquaInspect frontend connected to Flask backend. */

(function () {
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

  const API_BASE_URL = 'http://127.0.0.1:5000/api';
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // ==========================================
  // GENERAL HELPERS
  // ==========================================

  const showNotice = (message) => {
    let notice = $('#global-notice');

    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'global-notice';
      notice.className = 'global-notice';
      document.body.appendChild(notice);
    }

    notice.textContent = message;
    notice.classList.add('visible');

    clearTimeout(window.noticeTimer);
    window.noticeTimer = setTimeout(
      () => notice.classList.remove('visible'),
      4200
    );
  };

  const setError = (id, message) => {
    const error = $(`[data-error-for="${id}"]`);
    if (error) error.textContent = message;

    const input = $('#' + id);
    if (input) {
      input.setAttribute('aria-invalid', message ? 'true' : 'false');
    }
  };

  const clearErrors = (form) => {
    $$('.field-error', form).forEach((el) => {
      el.textContent = '';
    });

    $$('input', form).forEach((el) => {
      el.removeAttribute('aria-invalid');
    });
  };

  // ==========================================
  // API RESPONSE HANDLER
  // ==========================================

  const readApiResponse = async (response) => {
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const details = Array.isArray(data.details)
        ? data.details.map(item => item.reason || item.filename).join(', ')
        : '';

      throw new Error(
        data.message ||
        data.error ||
        data.msg ||
        details ||
        `Request failed (${response.status})`
      );
    }

    return data;
  };

  const authenticatedFetch = async (endpoint, options = {}) => {
    const token = sessionStorage.getItem('aquainspect-token');

    if (!token) {
      throw new Error('Authentication token not found. Please sign in again.');
    }

    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`
    };

    return fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers
    });
  };

  // ==========================================
  // YOLO ANALYSIS HELPERS
  // ==========================================

  const apiEndpointFromUrl = (url) => {
    if (!url) return '';

    if (/^https?:\/\//i.test(url)) {
      const parsed = new URL(url);
      return parsed.pathname.replace(/^\/api/, '') + parsed.search;
    }

    return String(url).replace(/^\/api/, '');
  };

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  const getInspectionImages = async (inspectionId) => {
    const response = await authenticatedFetch(
      `/inspections/${inspectionId}/images`
    );

    const data = await readApiResponse(response);

    return Array.isArray(data)
      ? data
      : (data.images || data.items || []);
  };

  // ==========================================
  // DISPLAY ANALYSIS RESULTS
  // ==========================================

  const renderAnalysisResults = async (
    inspectionId,
    images,
    detections
  ) => {
    let container = $('#analysis-results');

    if (!container) {
      container = document.createElement('section');
      container.id = 'analysis-results';

      container.style.cssText =
        'margin-top:20px;padding:18px;border:1px solid #dbe3ee;border-radius:12px;background:#fff;';

      const host = $('#video-preview') || $('#inspection-form');

      if (host) {
        host.insertAdjacentElement('afterend', container);
      } else {
        document.body.appendChild(container);
      }
    }

    container.replaceChildren();

    const heading = document.createElement('h3');
    heading.textContent =
      `Analysis results — Inspection #${inspectionId}`;

    container.appendChild(heading);

    const summary = document.createElement('p');
    summary.textContent =
      `${detections.length} defect(s) detected across ${images.length} image(s). GPS coordinates are not available from the current backend.`;

    container.appendChild(summary);

    // Defect table

    const table = document.createElement('table');
    table.style.cssText =
      'width:100%;border-collapse:collapse;margin:12px 0;';

    const thead = document.createElement('thead');
    const header = document.createElement('tr');

    [
      'Defect type',
      'Severity',
      'Confidence',
      'Detected at',
      'GPS'
    ].forEach(label => {
      const th = document.createElement('th');
      th.textContent = label;
      th.style.cssText =
        'text-align:left;padding:9px;border-bottom:1px solid #dbe3ee;';
      header.appendChild(th);
    });

    thead.appendChild(header);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    detections.forEach(item => {
      const row = document.createElement('tr');
      const confidence = Number(item.confidence);

      const values = [
        item.defect_type || item.class_name || 'Unknown',
        item.severity_level || item.severity || 'Not specified',
        Number.isFinite(confidence)
          ? `${(confidence <= 1 ? confidence * 100 : confidence).toFixed(1)}%`
          : '—',
        item.created_at
          ? new Date(item.created_at).toLocaleString()
          : '—',
        'Not available'
      ];

      values.forEach(value => {
        const cell = document.createElement('td');
        cell.textContent = String(value);
        cell.style.cssText =
          'padding:9px;border-bottom:1px solid #edf1f6;';
        row.appendChild(cell);
      });

      tbody.appendChild(row);
    });

    if (!detections.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');

      cell.colSpan = 5;
      cell.textContent =
        'No defects were detected in the analyzed images.';

      cell.style.padding = '10px';

      row.appendChild(cell);
      tbody.appendChild(row);
    }

    table.appendChild(tbody);
    container.appendChild(table);

    // Annotated images

    const imageTitle = document.createElement('h4');
    imageTitle.textContent = 'Annotated inspection images';
    container.appendChild(imageTitle);

    const grid = document.createElement('div');
    grid.style.cssText =
      'display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;';

    container.appendChild(grid);

    for (const image of images) {
      const imageId = image.id ?? image.image_id;

      const url =
        image.annotated_url ||
        image.image_annotated_url ||
        (imageId != null
          ? `/api/images/${imageId}/annotated`
          : '');

      if (!url) continue;

      const card = document.createElement('figure');
      card.style.cssText =
        'margin:0;padding:10px;border:1px solid #e5eaf1;border-radius:10px;';

      const caption = document.createElement('figcaption');
      caption.textContent =
        image.filename ||
        image.original_filename ||
        `Image ${imageId ?? ''}`;

      card.appendChild(caption);

      try {
        const response = await authenticatedFetch(
          apiEndpointFromUrl(url)
        );

        if (!response.ok) {
          throw new Error(`Image request failed (${response.status})`);
        }

        const objectUrl = URL.createObjectURL(
          await response.blob()
        );

        window.aquaInspectObjectUrls =
          window.aquaInspectObjectUrls || [];

        window.aquaInspectObjectUrls.push(objectUrl);

        const img = document.createElement('img');
        img.src = objectUrl;
        img.alt = 'YOLO annotated pipeline image';

        img.style.cssText =
          'display:block;width:100%;height:auto;margin-top:8px;border-radius:8px;';

        card.appendChild(img);

      } catch (error) {
        const note = document.createElement('p');
        note.textContent =
          `Annotated image unavailable: ${error.message}`;
        card.appendChild(note);
      }

      grid.appendChild(card);
    }
  };

  // ==========================================
  // START AND MONITOR YOLO ANALYSIS
  // ==========================================

  const runInspectionAnalysis = async (
    inspectionId,
    message,
    badge
  ) => {
    if (message) {
      message.textContent = 'Starting YOLO defect analysis...';
    }

    if (badge) badge.textContent = 'Analyzing...';

    const start = await authenticatedFetch(
      `/inspections/${inspectionId}/analyze`,
      { method: 'POST' }
    );

    await readApiResponse(start);

    let images = [];
    let complete = false;

    const deadline = Date.now() + 120000;

    while (Date.now() < deadline) {
      images = await getInspectionImages(inspectionId);

      if (images.length) {
        const states = images.map(item =>
          String(item.status || '').toLowerCase()
        );

        complete = states.every(state =>
          [
            'analyzed',
            'completed',
            'complete',
            'failed',
            'error'
          ].includes(state)
        );

        if (complete) break;
      }

      if (message) {
        message.textContent =
          'YOLO is analyzing the uploaded images. Please wait...';
      }

      await sleep(1800);
    }

    if (!complete) {
      throw new Error(
        'Analysis is taking longer than expected. Refresh this inspection later to check its status.'
      );
    }

    const failed = images.filter(item =>
      ['failed', 'error'].includes(
        String(item.status || '').toLowerCase()
      )
    );

    if (failed.length === images.length) {
      throw new Error(
        'The backend could not analyze these images. Check the backend logs.'
      );
    }

    const response = await authenticatedFetch(
      `/inspections/${inspectionId}/detections`
    );

    const data = await readApiResponse(response);

    const detections = Array.isArray(data)
      ? data
      : (
          data.items ||
          data.detections ||
          data.results ||
          []
        );

    await renderAnalysisResults(
      inspectionId,
      images,
      detections
    );

    if (message) {
      message.className = 'form-message success';
      message.textContent =
        `Analysis completed. ${detections.length} defect(s) detected.`;
    }

    if (badge) badge.textContent = 'Analysis complete';
  };

  // ==========================================
  // USERNAME HELPER
  // ==========================================

  const createUsername = (name) => {
    let username = name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 50);

    if (username.length < 3) {
      username = (username + '_001').slice(0, 50);
    }

    return username;
  };

  // ==========================================
  // DATA EXTRACTION & FORMATTING HELPERS
  // ==========================================

  const extractPipelineId = (notes, title, id) => {
    if (notes) {
      const match = String(notes).match(/Pipeline\s*ID\s*:\s*([^\r\n]+)/i);
      if (match && match[1].trim()) return match[1].trim();
    }
    if (title) {
      const match = String(title).match(/Pipeline\s+([^\r\n]+)/i);
      if (match && match[1].trim()) return match[1].trim();
    }
    return id ? `PL-${id}` : '—';
  };

  const extractInspectionDate = (notes, createdAt) => {
    if (notes) {
      const match = String(notes).match(/Inspection\s*Date\s*:\s*([^\r\n]+)/i);
      if (match && match[1].trim()) return match[1].trim();
    }
    if (createdAt) {
      try {
        const d = new Date(createdAt);
        if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
      } catch {}
      return String(createdAt).slice(0, 10);
    }
    return '—';
  };

  const capitalize = (text) => {
    if (!text) return '';
    return String(text).charAt(0).toUpperCase() + String(text).slice(1);
  };

  const formatDefectType = (type) => {
    if (!type) return 'Unknown';
    const normalized = String(type).replace(/[_\-\s]+/g, ' ').toLowerCase();
    if (normalized.includes('crack')) return 'Crack';
    if (normalized.includes('joint')) return 'Joint displacement';
    if (normalized.includes('corrosion')) return 'Corrosion';
    if (normalized.includes('blockage') || normalized.includes('debris')) return 'Blockage';
    return capitalize(normalized);
  };

  const formatSeverity = (level) => {
    if (!level) return 'Normal';
    const l = String(level).toLowerCase();
    if (l === 'critical') return 'Critical';
    if (l === 'high') return 'High';
    if (l === 'medium' || l === 'moderate') return 'Moderate';
    if (l === 'low' || l === 'minor') return 'Minor';
    if (l === 'normal') return 'Normal';
    return capitalize(l);
  };

  const getSeverityPillClass = (level) => {
    const l = String(level || '').toLowerCase();
    if (l === 'critical') return 'severity-critical';
    if (l === 'high') return 'severity-high';
    if (l === 'medium' || l === 'moderate') return 'severity-moderate';
    if (l === 'low' || l === 'minor' || l === 'normal') return 'severity-minor';
    return 'severity-minor';
  };

  const getStatusPillClass = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'completed') return 'status-completed';
    if (s === 'uploaded') return 'status-uploaded';
    if (s === 'processing') return 'status-processing';
    if (s === 'partial') return 'status-partial';
    if (s === 'failed') return 'status-failed';
    return 'neutral';
  };

  const fetchImageBlobUrl = async (url) => {
    const endpoint = apiEndpointFromUrl(url);
    const response = await authenticatedFetch(endpoint);
    if (!response.ok) {
      throw new Error(`Failed to load image (${response.status})`);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    window.aquaInspectObjectUrls = window.aquaInspectObjectUrls || [];
    window.aquaInspectObjectUrls.push(objectUrl);
    return objectUrl;
  };

  // ==========================================
  // REUSABLE DETAILS MODAL
  // ==========================================

  const appModal = $('#app-modal');
  const modalTitle = $('#modal-title');
  const modalBody = $('#modal-body');
  const modalCloseBtn = $('#modal-close-btn');

  const openModal = (title, contentElementOrHtml) => {
    if (!appModal || !modalBody || !modalTitle) return;
    modalTitle.textContent = title;
    if (typeof contentElementOrHtml === 'string') {
      modalBody.innerHTML = contentElementOrHtml;
    } else {
      modalBody.replaceChildren(contentElementOrHtml);
    }
    appModal.style.display = 'flex';
  };

  const closeModal = () => {
    if (!appModal) return;
    appModal.style.display = 'none';
    if (modalBody) modalBody.replaceChildren();
  };

  modalCloseBtn?.addEventListener('click', closeModal);
  appModal?.addEventListener('click', (event) => {
    if (event.target === appModal) closeModal();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && appModal?.style.display === 'flex') {
      closeModal();
    }
  });

  // Password visibility toggling
  $$('[data-toggle-password]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = $('#' + button.dataset.togglePassword);
      if (!input) return;
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      button.textContent = visible ? 'Show' : 'Hide';
      button.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
    });
  });

  // ==========================================
  // GENERAL NOTICES
  // ==========================================

  $$('[data-notice]').forEach(element => {
    element.addEventListener('click', () => {
      showNotice(element.dataset.notice);
    });
  });

  // ==========================================
  // LOGIN FORM
  // ==========================================

  const loginForm = $('#login-form');

  loginForm?.addEventListener('submit', async (event) => {
    event.preventDefault();

    clearErrors(loginForm);

    const loginIdentifier = $('#login-email')?.value.trim();
    const password = $('#login-password')?.value;

    let valid = true;

    if (!loginIdentifier) {
      setError('login-email', 'Email address or username is required.');
      valid = false;
    }

    if (!password) {
      setError('login-password', 'Password is required.');
      valid = false;
    }

    if (!valid) return;

    const button = $('button[type="submit"]', loginForm);

    if (button) {
      button.disabled = true;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: loginIdentifier,
          password: password
        })
      });

      const data = await readApiResponse(response);

      const token = data.access_token;

      if (!token) {
        throw new Error('Authentication token was not received.');
      }

      sessionStorage.setItem('aquainspect-token', token);

      if (data.user) {
        sessionStorage.setItem(
          'aquainspect-user',
          JSON.stringify(data.user)
        );
      }

      showNotice('Login successful!');

      window.location.href = 'dashboard.html';

    } catch (error) {
      console.error('Login error:', error);

      setError(
        'login-password',
        error.message || 'Invalid login credentials.'
      );

    } finally {
      if (button) {
        button.disabled = false;
      }
    }
  });

  // ==========================================
  // SIGNUP FORM
  // ==========================================

  const signupForm = $('#signup-form');

  signupForm?.addEventListener('submit', async event => {
    event.preventDefault();

    clearErrors(signupForm);

    const name =
      $('#signup-name')?.value.trim() ||
      $('#register-name')?.value.trim();

    const email =
      $('#signup-email')?.value.trim() ||
      $('#register-email')?.value.trim();

    const password =
      $('#signup-password')?.value ||
      $('#register-password')?.value;

    const confirmPassword =
      $('#signup-confirm-password')?.value ||
      $('#register-confirm-password')?.value;

    let valid = true;

    if (!name) {
      setError('signup-name', 'Name is required.');
      valid = false;
    }

    if (!email || !emailPattern.test(email)) {
      setError('signup-email', 'Enter a valid email address.');
      valid = false;
    }

    if (!password || password.length < 8) {
      setError('signup-password', 'Password must contain at least 8 characters.');
      valid = false;
    }

    if (confirmPassword && password !== confirmPassword) {
      setError('signup-confirm-password', 'Passwords do not match.');
      valid = false;
    }

    if (!valid) return;

    const button = $('button[type="submit"]', signupForm);
    if (button) button.disabled = true;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name,
          username: createUsername(name),
          email,
          password
        })
      });

      await readApiResponse(response);

      showNotice('Account created successfully. Please sign in.');

      window.location.href = 'login.html';

    } catch (error) {
      console.error('Signup error:', error);
      showNotice(error.message || 'Registration failed.');
    } finally {
      if (button) button.disabled = false;
    }
  });

  // ==========================================
  // AUTHENTICATION AND USER SESSION
  // ==========================================

  const logoutButtons = $$(
    '#logout, #logout-button, [data-logout]'
  );

  logoutButtons.forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();

      sessionStorage.removeItem('aquainspect-token');
      sessionStorage.removeItem('aquainspect-user');

      showNotice('You have been logged out.');

      window.location.href = 'login.html';
    });
  });

  const loadCurrentUser = async () => {
    const token = sessionStorage.getItem('aquainspect-token');

    if (!token) return;

    try {
      const response = await authenticatedFetch('/auth/me');
      const data = await readApiResponse(response);

      const user = data.user || data;

      sessionStorage.setItem(
        'aquainspect-user',
        JSON.stringify(user)
      );

      const name =
        user.name ||
        user.username ||
        user.email ||
        'User';

      $$('#user-name, #profile-name, [data-user-name]').forEach(el => {
        el.textContent = name;
      });

    } catch (error) {
      console.error('User session error:', error);
    }
  };

  loadCurrentUser();

  // ==========================================
  // DASHBOARD API STATUS
  // ==========================================

  const setApiStatus = (connected, message) => {
    const dot = $('#api-status-dot');
    const text = $('#api-status-text');

    if (dot) {
      dot.classList.toggle('online', connected);
      dot.classList.toggle('offline', !connected);
    }

    if (text) {
      text.textContent = message;
    }
  };

  const setStat = (id, value, captionId, caption) => {
    const element = $('#' + id);
    const captionElement = $('#' + captionId);

    if (element) {
      element.textContent = value;
    }

    if (captionElement) {
      captionElement.textContent = caption;
    }
  };

  const loadDashboardSummary = async () => {
    if (!$('#stat-total-inspections')) return;

    const token = sessionStorage.getItem('aquainspect-token');

    if (!token) {
      setApiStatus(false, 'Not authenticated');
      return;
    }

    try {
      const healthResponse = await fetch(`${API_BASE_URL}/health`);
      await readApiResponse(healthResponse);

      const response = await authenticatedFetch('/dashboard/summary');
      const data = await readApiResponse(response);

      setApiStatus(true, 'Connected');

      setStat(
        'stat-total-inspections',
        data.total_inspections ?? 0,
        'stat-inspections-caption',
        'Total saved inspections'
      );

      setStat(
        'stat-total-defects',
        data.total_defects_detected ?? 0,
        'stat-defects-caption',
        'Total detected defects'
      );

      setStat(
        'stat-images-analyzed',
        data.total_images_analyzed ?? 0,
        'stat-analyzed-caption',
        'Images successfully analyzed'
      );

      setStat(
        'stat-images-with-defects',
        data.images_with_defects ?? 0,
        'stat-images-caption',
        'Images containing defects'
      );

    } catch (error) {
      console.error('Dashboard API error:', error);

      setApiStatus(false, 'Connection error');

      [
        ['stat-total-inspections', 'stat-inspections-caption'],
        ['stat-total-defects', 'stat-defects-caption'],
        ['stat-images-analyzed', 'stat-analyzed-caption'],
        ['stat-images-with-defects', 'stat-images-caption']
      ].forEach(([id, captionId]) => {
        setStat(id, '—', captionId, 'Unable to load data');
      });

      if (
        error.message.includes('401') ||
        error.message.includes('422')
      ) {
        setApiStatus(false, 'Session expired');
      }
    }
  };

  window.loadDashboardSummary = loadDashboardSummary;
  loadDashboardSummary();

  // ==========================================
  // DASHBOARD NAVIGATION
  // ==========================================

  const pageSections = $$('.page-section');
  const navigationLinks = $$('.nav-link[data-section]');
  const pageTitle = $('#page-title');
  const sidebar = $('#sidebar');

  const activateSection = (sectionId) => {
    const targetSection = document.getElementById(sectionId);

    if (
      !targetSection ||
      !targetSection.classList.contains('page-section')
    ) {
      return;
    }

    pageSections.forEach((section) => {
      section.classList.toggle(
        'active-section',
        section === targetSection
      );
    });

    navigationLinks.forEach((link) => {
      link.classList.toggle(
        'active',
        link.dataset.section === sectionId
      );
    });

    const activeLink = navigationLinks.find(
      (link) => link.dataset.section === sectionId
    );

    if (pageTitle && activeLink) {
      pageTitle.textContent = activeLink.textContent.trim();
    }

    if (window.location.hash !== `#${sectionId}`) {
      history.replaceState(null, '', `#${sectionId}`);
    }

    sidebar?.classList.remove('open');

    if (sectionId === 'overview') {
      loadDashboardSummary();
    } else if (sectionId === 'defects') {
      loadDefectAnalysis();
    } else if (sectionId === 'history') {
      loadInspectionHistory();
    } else if (sectionId === 'reports') {
      loadInspectionReports();
    }

    if (sectionId === 'map' && window.inspectionMap) {
      window.setTimeout(() => {
        window.inspectionMap.invalidateSize();
      }, 150);
    }
  };

  if (pageSections.length) {
    navigationLinks.forEach((link) => {
      link.addEventListener('click', (event) => {
        event.preventDefault();
        activateSection(link.dataset.section);
      });
    });

    $$('[data-section-jump]').forEach((element) => {
      element.addEventListener('click', (event) => {
        event.preventDefault();
        activateSection(element.dataset.sectionJump);
      });
    });

    window.addEventListener('hashchange', () => {
      activateSection(window.location.hash.slice(1) || 'overview');
    });

    activateSection(
      window.location.hash.slice(1) || 'overview'
    );
  }

  // ==========================================
  // MOBILE SIDEBAR
  // ==========================================

  $('#menu-toggle')?.addEventListener('click', (event) => {
    event.preventDefault();
    sidebar?.classList.toggle('open');
  });

  $('#sidebar-close')?.addEventListener('click', (event) => {
    event.preventDefault();
    sidebar?.classList.remove('open');
  });

  document.addEventListener('click', (event) => {
    if (!sidebar?.classList.contains('open') || window.innerWidth > 760) {
      return;
    }

    if (
      sidebar.contains(event.target) ||
      $('#menu-toggle')?.contains(event.target)
    ) {
      return;
    }

    sidebar.classList.remove('open');
  });

  // ==========================================
  // IMAGE PREVIEW AND BACKEND UPLOAD
  // ==========================================

  const fileInput = $('#video-file');
  const choose = $('#choose-video');
  const zone = $('#upload-zone');
  const preview = $('#video-preview');
  const fileName = $('#file-name');
  const badge = $('#processing-badge');
  const inspectionForm = $('#inspection-form');
  const inspectionMessage = $('#inspection-message');

  let selectedImages = [];
  let previewUrls = [];

  if (fileInput && choose && zone) {
    choose.addEventListener('click', () => fileInput.click());

    zone.addEventListener('click', event => {
      if (event.target === zone) fileInput.click();
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      zone.addEventListener(eventName, event => {
        event.preventDefault();
        zone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      zone.addEventListener(eventName, event => {
        event.preventDefault();
        zone.classList.remove('dragover');
      });
    });

    zone.addEventListener('drop', event => {
      handleSelectedImages(Array.from(event.dataTransfer.files));
    });

    fileInput.addEventListener('change', () => {
      handleSelectedImages(Array.from(fileInput.files));
    });

    const clearPreviewUrls = () => {
      previewUrls.forEach(url => URL.revokeObjectURL(url));
      previewUrls = [];
    };

    function handleSelectedImages(files) {
      if (!files.length) return;

      const allowedTypes = [
        'image/jpeg',
        'image/png',
        'image/jpg'
      ];

      if (files.some(file => !allowedTypes.includes(file.type))) {
        showNotice('Only JPG, JPEG and PNG images are supported.');
        fileInput.value = '';
        return;
      }

      if (files.length > 50) {
        showNotice('Maximum 50 images can be uploaded at once.');
        fileInput.value = '';
        return;
      }

      selectedImages = files;
      clearPreviewUrls();

      if (preview) preview.innerHTML = '';

      files.forEach(file => {
        const image = document.createElement('img');
        const url = URL.createObjectURL(file);

        previewUrls.push(url);

        image.src = url;
        image.alt = `Pipeline image: ${file.name}`;
        image.style.maxWidth = '100%';
        image.style.height = 'auto';

        preview?.appendChild(image);
      });

      if (fileName) {
        fileName.textContent = `${files.length} image(s) selected`;
      }

      if (badge) badge.textContent = 'Ready';

      if (inspectionMessage) {
        inspectionMessage.textContent = '';
      }
    }

    // ==========================================
    // SUBMIT INSPECTION
    // ==========================================

    inspectionForm?.addEventListener('submit', async event => {
      event.preventDefault();

      const pipelineId = $('#pipeline-id')?.value.trim();
      const location = $('#inspection-location')?.value.trim();
      const inspectionDate = $('#inspection-date')?.value;

      if (!pipelineId || !location || !inspectionDate) {
        showNotice('Please complete the required inspection details.');
        return;
      }

      if (!selectedImages.length) {
        showNotice('Please select at least one pipeline image.');
        return;
      }

      const token = sessionStorage.getItem('aquainspect-token');

      if (!token) {
        showNotice('Session expired. Please sign in again.');
        window.location.href = 'login.html';
        return;
      }

      const submitButton = $('button[type="submit"]', inspectionForm);

      if (submitButton) submitButton.disabled = true;
      if (badge) badge.textContent = 'Uploading...';

      if (inspectionMessage) {
        inspectionMessage.className = 'form-message';
        inspectionMessage.textContent =
          'Uploading images to AquaInspect...';
      }

      try {
        const formData = new FormData();

        formData.append('title', `Pipeline ${pipelineId}`);
        formData.append('location', location);

        formData.append(
          'notes',
          `Pipeline ID: ${pipelineId}\nInspection Date: ${inspectionDate}`
        );

        selectedImages.forEach(file => {
          formData.append('images', file);
        });

        const response = await authenticatedFetch(
          '/inspections/upload',
          {
            method: 'POST',
            body: formData
          }
        );

        const data = await readApiResponse(response);

        const inspectionId = data.inspection?.id;
        const uploadedCount = data.images?.length || 0;
        const rejectedCount = data.rejected?.length || 0;

        if (inspectionId !== undefined && inspectionId !== null) {
          sessionStorage.setItem(
            'aquainspect-last-inspection-id',
            String(inspectionId)
          );
        }

        if (badge) badge.textContent = 'Uploaded';

        if (inspectionMessage) {
          inspectionMessage.className = 'form-message success';

          inspectionMessage.textContent =
            `${uploadedCount} image(s) uploaded successfully. Inspection ID: ${inspectionId ?? 'created'}.` +
            (rejectedCount ? ` ${rejectedCount} image(s) rejected.` : '');
        }

        if (inspectionId === undefined || inspectionId === null) {
          throw new Error(
            'Upload succeeded, but the server did not return an inspection ID.'
          );
        }

        showNotice('Images uploaded. Starting YOLO analysis...');

        // Automatically start YOLO analysis after upload.

        await runInspectionAnalysis(
          inspectionId,
          inspectionMessage,
          badge
        );

        // Refresh dashboard cards and records.

        await loadDashboardSummary();
        await loadDefectAnalysis(true);
        await loadInspectionHistory(true);
        await loadInspectionReports();

        // Reset upload form after successful analysis.

        inspectionForm.reset();
        selectedImages = [];
        clearPreviewUrls();

        if (fileName) {
          fileName.textContent = 'No image selected';
        }

        if (preview) {
          preview.innerHTML =
            '<strong>Analysis completed</strong><p>Annotated results are displayed below.</p>';
        }

        if (rejectedCount) {
          console.warn('Rejected images:', data.rejected);

          showNotice(
            `${rejectedCount} image(s) were rejected. Check the browser console for details.`
          );
        }

      } catch (error) {
        console.error('Inspection upload error:', error);

        if (badge) badge.textContent = 'Upload failed';

        if (inspectionMessage) {
          inspectionMessage.className = 'form-message error';
          inspectionMessage.textContent =
            error.message || 'Image upload failed. Please try again.';
        }

      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  // ==========================================
  // MAP PLACEHOLDER
  // ==========================================

  if ($('#inspection-map') && window.L) {
    const map = L.map('inspection-map', {
      zoomControl: true,
      attributionControl: true
    }).setView([20, 0], 2);

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }
    ).addTo(map);

    window.inspectionMap = map;
  }

  // ==========================================
  // FILTER MATCHING HELPERS
  // ==========================================

  const matchesDefectTypeFilter = (itemDefectType, filterValue) => {
    if (!filterValue) return true;
    const cleanItem = String(itemDefectType || '').toLowerCase().replace(/[_\-\s]+/g, '');
    const cleanFilter = String(filterValue).toLowerCase().replace(/[_\-\s]+/g, '').replace(/s$/, '');
    return cleanItem.includes(cleanFilter) || cleanFilter.includes(cleanItem);
  };

  const matchesSeverityFilter = (itemSeverity, filterValue) => {
    if (!filterValue) return true;
    const s = String(itemSeverity || '').toLowerCase();
    const f = String(filterValue).toLowerCase();

    if (f === 'critical') {
      return s === 'critical';
    }
    if (f === 'moderate' || f === 'medium') {
      return s === 'moderate' || s === 'medium' || s === 'high';
    }
    if (f === 'minor' || f === 'low') {
      return s === 'minor' || s === 'low';
    }
    if (f === 'normal') {
      return s === 'normal' || !s;
    }
    return s === f;
  };

  // ==========================================
  // FEATURE 1: DEFECT ANALYSIS
  // ==========================================

  let allDetectionsList = [];
  let defectAnalysisLoaded = false;

  async function loadDefectAnalysis(force = false) {
    const tableBody = $('#defect-table-body');
    if (!tableBody) return;

    if (defectAnalysisLoaded && !force) {
      renderDefectTable();
      return;
    }

    const token = sessionStorage.getItem('aquainspect-token');
    if (!token) return;

    tableBody.innerHTML = `
      <tr class="loading-row">
        <td colspan="8">
          <div class="table-loading">
            <span class="loading-spinner"></span>
            <span>Loading defect analysis records...</span>
          </div>
        </td>
      </tr>
    `;

    try {
      // 1. Fetch inspections (with pagination)
      let inspections = [];
      let page = 1;
      let totalPages = 1;

      while (page <= totalPages && page <= 5) {
        const resp = await authenticatedFetch(`/inspections?page=${page}&per_page=100`);
        const data = await readApiResponse(resp);
        const items = data.items || [];
        inspections = inspections.concat(items);
        totalPages = data.pages || 1;
        page++;
      }

      // 2. For every inspection with detection_count > 0, fetch detections
      const inspectionsWithDefects = inspections.filter(i => (i.detection_count || 0) > 0);
      const detectionPromises = inspectionsWithDefects.map(async (insp) => {
        try {
          const resp = await authenticatedFetch(`/inspections/${insp.id}/detections?per_page=100`);
          const data = await readApiResponse(resp);
          const detections = data.items || [];
          return detections.map(d => ({
            ...d,
            pipelineId: extractPipelineId(insp.notes, insp.title, insp.id),
            inspectionLocation: insp.location || '—',
            inspectionDate: extractInspectionDate(insp.notes, insp.created_at),
            inspectionTitle: insp.title || `Inspection #${insp.id}`
          }));
        } catch (err) {
          console.warn(`Failed to fetch detections for inspection ${insp.id}:`, err);
          return [];
        }
      });

      const results = await Promise.all(detectionPromises);
      allDetectionsList = results.flat();
      defectAnalysisLoaded = true;
      renderDefectTable();

    } catch (error) {
      console.error('Failed to load defect analysis:', error);
      tableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="8">
            <strong style="color:var(--red);">Error loading defect records</strong>
            <span>${error.message || 'Unable to retrieve detections from server.'}</span>
          </td>
        </tr>
      `;
    }
  }

  function renderDefectTable() {
    const tableBody = $('#defect-table-body');
    if (!tableBody) return;

    const searchTerm = ($('#defect-search')?.value || '').trim().toLowerCase();
    const severityFilter = ($('#defect-severity')?.value || '').trim();
    const typeFilter = ($('#defect-type')?.value || '').trim();

    const filtered = allDetectionsList.filter(item => {
      const pipeline = String(item.pipelineId || '').toLowerCase();
      const defectType = String(item.defect_type || '').toLowerCase();
      const formattedType = formatDefectType(item.defect_type).toLowerCase();
      const defectId = String(item.id || '');
      const severity = String(item.severity_level || '').toLowerCase();

      const matchesSearch = !searchTerm ||
        pipeline.includes(searchTerm) ||
        defectType.includes(searchTerm) ||
        formattedType.includes(searchTerm) ||
        defectId.includes(searchTerm) ||
        `#${defectId}`.includes(searchTerm) ||
        severity.includes(searchTerm);

      const matchesSeverity = matchesSeverityFilter(item.severity_level, severityFilter);
      const matchesType = matchesDefectTypeFilter(item.defect_type, typeFilter);

      return matchesSearch && matchesSeverity && matchesType;
    });

    if (!filtered.length) {
      tableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="8">
            <strong>${allDetectionsList.length === 0 ? 'No defects detected yet.' : 'No matching defects found.'}</strong>
            <span>${allDetectionsList.length === 0 ? 'Analysis results will appear here when received from the API.' : 'Try adjusting your search or filter options.'}</span>
          </td>
        </tr>
      `;
      return;
    }

    tableBody.replaceChildren();

    filtered.forEach(d => {
      const row = document.createElement('tr');
      const conf = Number(d.confidence);
      const confFormatted = Number.isFinite(conf)
        ? `${(conf <= 1 ? conf * 100 : conf).toFixed(1)}%`
        : '—';

      const timeFormatted = d.created_at
        ? new Date(d.created_at).toLocaleString()
        : '—';

      row.innerHTML = `
        <td><strong>#${d.id}</strong></td>
        <td>${d.pipelineId}</td>
        <td>${formatDefectType(d.defect_type)}</td>
        <td><span class="severity-pill ${getSeverityPillClass(d.severity_level)}">${formatSeverity(d.severity_level)}</span></td>
        <td>${confFormatted}</td>
        <td>${timeFormatted}</td>
        <td>Not available</td>
        <td>
          <button class="button button-secondary button-small btn-view-defect" data-defect-id="${d.id}">
            View
          </button>
        </td>
      `;

      $('.btn-view-defect', row)?.addEventListener('click', () => {
        showDefectModal(d);
      });

      tableBody.appendChild(row);
    });
  }

  async function showDefectModal(defect) {
    const content = document.createElement('div');
    const conf = Number(defect.confidence);
    const confFormatted = Number.isFinite(conf)
      ? `${(conf <= 1 ? conf * 100 : conf).toFixed(1)}%`
      : '—';

    content.innerHTML = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:12px; margin-bottom:18px;">
        <div class="report-meta-item">
          <small>Defect ID</small>
          <strong>#${defect.id}</strong>
        </div>
        <div class="report-meta-item">
          <small>Pipeline ID</small>
          <strong>${defect.pipelineId || '—'}</strong>
        </div>
        <div class="report-meta-item">
          <small>Defect Type</small>
          <strong>${formatDefectType(defect.defect_type)}</strong>
        </div>
        <div class="report-meta-item">
          <small>Severity</small>
          <strong><span class="severity-pill ${getSeverityPillClass(defect.severity_level)}">${formatSeverity(defect.severity_level)}</span></strong>
        </div>
        <div class="report-meta-item">
          <small>Confidence</small>
          <strong>${confFormatted}</strong>
        </div>
        <div class="report-meta-item">
          <small>Inspection ID</small>
          <strong>#${defect.inspection_id}</strong>
        </div>
        <div class="report-meta-item">
          <small>GPS Coordinates</small>
          <strong>Not available</strong>
        </div>
        <div class="report-meta-item">
          <small>Timestamp</small>
          <strong>${defect.created_at ? new Date(defect.created_at).toLocaleString() : '—'}</strong>
        </div>
      </div>
      <div id="defect-modal-image-container" style="text-align:center; padding:16px; background:#f1f5f9; border-radius:8px; min-height:220px; display:flex; align-items:center; justify-content:center; flex-direction:column;">
        <span class="loading-spinner"></span>
        <span style="margin-top:8px; font-size:12px; color:var(--muted);">Loading annotated defect image...</span>
      </div>
    `;

    openModal(`Defect #${defect.id} — ${formatDefectType(defect.defect_type)}`, content);

    const imgContainer = $('#defect-modal-image-container', content);
    try {
      const imgUrl = defect.image_annotated_url || `/api/images/${defect.image_id}/annotated`;
      const blobUrl = await fetchImageBlobUrl(imgUrl);
      imgContainer.replaceChildren();
      const img = document.createElement('img');
      img.src = blobUrl;
      img.alt = `Annotated defect #${defect.id}`;
      img.style.cssText = 'max-width:100%; max-height:480px; object-fit:contain; border-radius:6px; box-shadow:0 4px 12px rgba(0,0,0,0.1);';
      imgContainer.appendChild(img);
    } catch (err) {
      imgContainer.innerHTML = `
        <p style="color:var(--muted); font-size:12px;">Annotated image unavailable: ${err.message}</p>
      `;
    }
  }

  // Export Results -> CSV Download
  async function exportDefectsCsv() {
    showNotice('Preparing detections CSV export...');
    try {
      const resp = await authenticatedFetch('/reports/export/csv');
      if (!resp.ok) {
        throw new Error(`CSV export failed (${resp.status})`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'detections_export.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showNotice('Detections CSV exported successfully.');
    } catch (err) {
      console.error('CSV export error:', err);
      showNotice(`Export failed: ${err.message}`);
    }
  }

  // ==========================================
  // FEATURE 2: INSPECTION HISTORY
  // ==========================================

  let allInspectionsList = [];
  let inspectionHistoryLoaded = false;
  const inspectionDetectionsCache = {};

  async function loadInspectionHistory(force = false) {
    const tableBody = $('#history-table-body');
    if (!tableBody) return;

    if (inspectionHistoryLoaded && !force) {
      renderHistoryTable();
      return;
    }

    const token = sessionStorage.getItem('aquainspect-token');
    if (!token) return;

    tableBody.innerHTML = `
      <tr class="loading-row">
        <td colspan="8">
          <div class="table-loading">
            <span class="loading-spinner"></span>
            <span>Loading inspection history...</span>
          </div>
        </td>
      </tr>
    `;

    try {
      let inspections = [];
      let page = 1;
      let totalPages = 1;

      while (page <= totalPages && page <= 5) {
        const resp = await authenticatedFetch(`/inspections?page=${page}&per_page=100`);
        const data = await readApiResponse(resp);
        const items = data.items || [];
        inspections = inspections.concat(items);
        totalPages = data.pages || 1;
        page++;
      }

      allInspectionsList = inspections.map(i => ({
        ...i,
        pipelineId: extractPipelineId(i.notes, i.title, i.id),
        inspectionDate: extractInspectionDate(i.notes, i.created_at)
      }));

      // Preload detections for inspections that have defect count > 0 for instant filtering
      const inspectionsWithDefects = allInspectionsList.filter(i => (i.detection_count || 0) > 0);
      await Promise.all(inspectionsWithDefects.map(async (insp) => {
        if (!inspectionDetectionsCache[insp.id]) {
          try {
            const resp = await authenticatedFetch(`/inspections/${insp.id}/detections?per_page=100`);
            const data = await readApiResponse(resp);
            inspectionDetectionsCache[insp.id] = data.items || [];
          } catch (e) {
            inspectionDetectionsCache[insp.id] = [];
          }
        }
      }));

      inspectionHistoryLoaded = true;
      renderHistoryTable();

    } catch (error) {
      console.error('Failed to load inspection history:', error);
      tableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="8">
            <strong style="color:var(--red);">Error loading inspection records</strong>
            <span>${error.message || 'Unable to retrieve inspections from server.'}</span>
          </td>
        </tr>
      `;
    }
  }

  function renderHistoryTable() {
    const tableBody = $('#history-table-body');
    if (!tableBody) return;

    const pipelineFilter = ($('#history-pipeline')?.value || '').trim().toLowerCase();
    const dateFilter = ($('#history-date')?.value || '').trim();
    const typeFilter = ($('#history-type')?.value || '').trim();
    const severityFilter = ($('#history-severity')?.value || '').trim();

    const filtered = allInspectionsList.filter(insp => {
      // Pipeline ID filter
      const pipeline = String(insp.pipelineId || '').toLowerCase();
      const matchesPipeline = !pipelineFilter ||
        pipeline.includes(pipelineFilter) ||
        String(insp.title || '').toLowerCase().includes(pipelineFilter) ||
        String(insp.id).includes(pipelineFilter);

      // Date filter
      const date = String(insp.inspectionDate || '');
      const matchesDate = !dateFilter || date.includes(dateFilter);

      // Defect type filter
      let matchesType = true;
      if (typeFilter) {
        const detections = inspectionDetectionsCache[insp.id] || [];
        matchesType = detections.some(d => matchesDefectTypeFilter(d.defect_type, typeFilter));
      }

      // Severity filter
      let matchesSeverity = true;
      if (severityFilter) {
        const detections = inspectionDetectionsCache[insp.id] || [];
        matchesSeverity = detections.some(d => matchesSeverityFilter(d.severity_level, severityFilter));
      }

      return matchesPipeline && matchesDate && matchesType && matchesSeverity;
    });

    if (!filtered.length) {
      tableBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="8">
            <div class="table-empty">
              <span class="empty-icon">◷</span>
              <strong>No records found.</strong>
              <p>${allInspectionsList.length === 0 ? 'Inspection history will populate from the API.' : 'No inspection records match your filter criteria.'}</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tableBody.replaceChildren();

    filtered.forEach(insp => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>#${insp.id}</strong></td>
        <td>${insp.pipelineId}</td>
        <td>${insp.location || '—'}</td>
        <td>${insp.inspectionDate}</td>
        <td>${insp.image_count ?? 0}</td>
        <td>${insp.detection_count ?? 0}</td>
        <td><span class="status-pill ${getStatusPillClass(insp.status)}">${capitalize(insp.status)}</span></td>
        <td>
          <button class="button button-secondary button-small btn-view-history" data-inspection-id="${insp.id}">
            View details
          </button>
        </td>
      `;

      $('.btn-view-history', row)?.addEventListener('click', () => {
        showInspectionDetailsModal(insp);
      });

      tableBody.appendChild(row);
    });
  }

  function showInspectionDetailsModal(insp) {
    const content = document.createElement('div');
    const detections = inspectionDetectionsCache[insp.id] || [];
    const isReportEligible = insp.status === 'completed' || insp.status === 'partial';

    content.innerHTML = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:12px; margin-bottom:20px;">
        <div class="report-meta-item">
          <small>Inspection ID</small>
          <strong>#${insp.id}</strong>
        </div>
        <div class="report-meta-item">
          <small>Pipeline ID</small>
          <strong>${insp.pipelineId}</strong>
        </div>
        <div class="report-meta-item">
          <small>Location</small>
          <strong>${insp.location || '—'}</strong>
        </div>
        <div class="report-meta-item">
          <small>Inspection Date</small>
          <strong>${insp.inspectionDate}</strong>
        </div>
        <div class="report-meta-item">
          <small>Status</small>
          <strong><span class="status-pill ${getStatusPillClass(insp.status)}">${capitalize(insp.status)}</span></strong>
        </div>
        <div class="report-meta-item">
          <small>Images Uploaded</small>
          <strong>${insp.image_count ?? 0}</strong>
        </div>
        <div class="report-meta-item">
          <small>Defects Found</small>
          <strong>${insp.detection_count ?? 0}</strong>
        </div>
        <div class="report-meta-item">
          <small>Model Version</small>
          <strong>${insp.model_version || 'Not analyzed'}</strong>
        </div>
      </div>

      <div style="margin-bottom:18px;">
        <h4 style="margin:0 0 8px; font-size:13px; color:var(--navy);">Inspection Notes</h4>
        <p style="margin:0; padding:10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; font-size:12px; white-space:pre-wrap;">${insp.notes || 'No notes provided.'}</p>
      </div>

      <div style="margin-bottom:18px;">
        <h4 style="margin:0 0 8px; font-size:13px; color:var(--navy);">Detections (${detections.length})</h4>
        ${detections.length === 0 ? '<p style="color:var(--muted); font-size:12px;">No defects detected in this inspection.</p>' : `
          <div class="table-wrap">
            <table style="width:100%;">
              <thead>
                <tr>
                  <th>Defect ID</th>
                  <th>Defect Type</th>
                  <th>Severity</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                ${detections.map(d => `
                  <tr>
                    <td>#${d.id}</td>
                    <td>${formatDefectType(d.defect_type)}</td>
                    <td><span class="severity-pill ${getSeverityPillClass(d.severity_level)}">${formatSeverity(d.severity_level)}</span></td>
                    <td>${(d.confidence <= 1 ? d.confidence * 100 : d.confidence).toFixed(1)}%</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>

      <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:20px; padding-top:16px; border-top:1px solid var(--line);">
        ${detections.length > 0 ? `
          <button class="button button-secondary button-small" id="btn-jump-defects">
            View in Defect Analysis
          </button>
        ` : ''}
        ${isReportEligible ? `
          <button class="button button-primary button-small" id="btn-modal-download-pdf">
            Download PDF Report
          </button>
        ` : ''}
      </div>
    `;

    openModal(`Inspection Details — #${insp.id}`, content);

    $('#btn-jump-defects', content)?.addEventListener('click', () => {
      closeModal();
      const defectSearch = $('#defect-search');
      if (defectSearch) {
        defectSearch.value = insp.pipelineId;
      }
      activateSection('defects');
      loadDefectAnalysis();
    });

    $('#btn-modal-download-pdf', content)?.addEventListener('click', () => {
      downloadInspectionPdf(insp.id, insp.pipelineId);
    });
  }

  // ==========================================
  // FEATURE 3: INSPECTION REPORTS
  // ==========================================

  let eligibleReportInspections = [];

  const getSessionReports = () => {
    try {
      return JSON.parse(sessionStorage.getItem('aquainspect-session-reports') || '[]');
    } catch {
      return [];
    }
  };

  const addSessionReport = (report) => {
    const list = getSessionReports();
    list.unshift(report);
    if (list.length > 20) list.length = 20;
    sessionStorage.setItem('aquainspect-session-reports', JSON.stringify(list));
    renderRecentReports();
  };

  function renderRecentReports() {
    const emptyState = $('#recent-reports-empty');
    const wrap = $('#recent-reports-wrap');
    const tbody = $('#recent-reports-body');
    if (!emptyState || !wrap || !tbody) return;

    const reports = getSessionReports();
    if (!reports.length) {
      emptyState.style.display = 'flex';
      wrap.style.display = 'none';
      return;
    }

    emptyState.style.display = 'none';
    wrap.style.display = 'block';
    tbody.replaceChildren();

    reports.forEach(r => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>
          <strong>Inspection #${r.inspectionId}</strong>
          <small style="display:block; color:var(--muted);">${r.pipelineId ? `Pipeline ${r.pipelineId}` : 'Pipeline report'}</small>
        </td>
        <td>${r.timestampFormatted || 'Recently'}</td>
        <td>
          <button class="button button-secondary button-small btn-redownload-report" data-inspection-id="${r.inspectionId}">
            Download
          </button>
        </td>
      `;

      $('.btn-redownload-report', row)?.addEventListener('click', () => {
        downloadInspectionPdf(r.inspectionId, r.pipelineId);
      });

      tbody.appendChild(row);
    });
  }

  function updateSelectedReportDetails() {
    const select = $('#report-inspection-select');
    const detailsContainer = $('#report-inspection-details');
    const generateBtn = $('#btn-generate-report');
    if (!select || !detailsContainer) return;

    const iid = Number(select.value);
    const insp = eligibleReportInspections.find(i => i.id === iid);
    if (!insp) {
      detailsContainer.innerHTML = '';
      if (generateBtn) generateBtn.disabled = true;
      return;
    }

    if (generateBtn) generateBtn.disabled = false;

    detailsContainer.innerHTML = `
      <div class="report-meta-grid">
        <div class="report-meta-item">
          <small>Inspection ID</small>
          <strong>#${insp.id}</strong>
        </div>
        <div class="report-meta-item">
          <small>Pipeline ID</small>
          <strong>${insp.pipelineId}</strong>
        </div>
        <div class="report-meta-item">
          <small>Location</small>
          <strong>${insp.location || '—'}</strong>
        </div>
        <div class="report-meta-item">
          <small>Inspection Date</small>
          <strong>${insp.inspectionDate}</strong>
        </div>
        <div class="report-meta-item">
          <small>Status</small>
          <strong><span class="status-pill ${getStatusPillClass(insp.status)}">${capitalize(insp.status)}</span></strong>
        </div>
        <div class="report-meta-item">
          <small>Images Analyzed</small>
          <strong>${insp.image_count ?? 0}</strong>
        </div>
        <div class="report-meta-item">
          <small>Defects Detected</small>
          <strong>${insp.detection_count ?? 0}</strong>
        </div>
        <div class="report-meta-item">
          <small>Report Status</small>
          <strong style="color:var(--green);">Ready for PDF generation</strong>
        </div>
      </div>
    `;
  }

  async function loadInspectionReports() {
    const emptyState = $('#reports-empty-state');
    const selectorWrap = $('#reports-selector-wrap');
    const select = $('#report-inspection-select');
    const generateBtn = $('#btn-generate-report');
    if (!emptyState || !selectorWrap || !select) return;

    renderRecentReports();

    const token = sessionStorage.getItem('aquainspect-token');
    if (!token) return;

    try {
      const resp = await authenticatedFetch('/inspections?per_page=100');
      const data = await readApiResponse(resp);
      const items = data.items || [];

      eligibleReportInspections = items
        .filter(i => i.status === 'completed' || i.status === 'partial')
        .map(i => ({
          ...i,
          pipelineId: extractPipelineId(i.notes, i.title, i.id),
          inspectionDate: extractInspectionDate(i.notes, i.created_at)
        }));

      if (!eligibleReportInspections.length) {
        emptyState.style.display = 'flex';
        selectorWrap.style.display = 'none';
        if (generateBtn) generateBtn.disabled = true;
        return;
      }

      emptyState.style.display = 'none';
      selectorWrap.style.display = 'block';

      select.replaceChildren();
      eligibleReportInspections.forEach(insp => {
        const option = document.createElement('option');
        option.value = String(insp.id);
        option.textContent = `Inspection #${insp.id} — Pipeline ${insp.pipelineId} (${insp.detection_count ?? 0} defect(s), ${insp.inspectionDate})`;
        select.appendChild(option);
      });

      updateSelectedReportDetails();

    } catch (error) {
      console.error('Failed to load inspection reports:', error);
    }
  }

  async function downloadInspectionPdf(inspectionId, pipelineId = '') {
    if (!inspectionId) return;

    const generateBtn = $('#btn-generate-report');
    const originalText = generateBtn ? generateBtn.textContent : '';
    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.textContent = 'Generating PDF...';
    }

    showNotice(`Generating PDF report for inspection #${inspectionId}...`);

    try {
      const resp = await authenticatedFetch(`/reports/${inspectionId}/pdf`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || errData.message || `Failed to generate PDF (${resp.status})`);
      }

      const blob = await resp.blob();
      const filename = `inspection_${inspectionId}_report.pdf`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      showNotice(`Report ${filename} downloaded successfully.`);

      addSessionReport({
        inspectionId,
        pipelineId: pipelineId || `PL-${inspectionId}`,
        timestampFormatted: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        filename
      });

    } catch (error) {
      console.error('PDF download error:', error);
      showNotice(`Report generation failed: ${error.message}`);
    } finally {
      if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.textContent = originalText;
      }
    }
  }

  // ==========================================
  // EVENT LISTENERS & FILTER BINDINGS
  // ==========================================

  // Defect Analysis filters
  ['defect-search', 'defect-severity', 'defect-type'].forEach(id => {
    const control = $('#' + id);
    control?.addEventListener('input', renderDefectTable);
    control?.addEventListener('change', renderDefectTable);
  });

  // Inspection History filters
  ['history-pipeline', 'history-date', 'history-type', 'history-severity'].forEach(id => {
    const control = $('#' + id);
    control?.addEventListener('input', renderHistoryTable);
    control?.addEventListener('change', renderHistoryTable);
  });

  // Export Defect Results (CSV)
  $$('[data-api-action="export-defects"]').forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      exportDefectsCsv();
    });
  });

  // Generate Report (PDF)
  $$('[data-api-action="generate-report"], #btn-generate-report').forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      const select = $('#report-inspection-select');
      if (select && select.value) {
        const iid = Number(select.value);
        const insp = eligibleReportInspections.find(i => i.id === iid);
        downloadInspectionPdf(iid, insp?.pipelineId);
      } else {
        showNotice('Please select an eligible inspection first.');
      }
    });
  });

  $('#report-inspection-select')?.addEventListener('change', updateSelectedReportDetails);

  // Other placeholder API actions (work orders, assets, system administration)
  $$('[data-api-action]:not([data-api-action="export-defects"]):not([data-api-action="generate-report"])').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      showNotice(
        'This feature will be enabled when its backend integration is completed.'
      );
    });
  });

  // Other placeholder filters
  $$('input[id^="work-"], select[id^="work-"], input[id^="asset-"]').forEach(control => {
    control.addEventListener('input', () => {
      showNotice(
        'This filter will be connected when its backend endpoint is available.'
      );
    });
  });

  // Initial load of all sections
  loadDefectAnalysis();
  loadInspectionHistory();
  loadInspectionReports();

})();