(() => {
  const modalInstances = new WeakMap();

  // Función de utilidad para limitar la frecuencia de ejecución (Debounce)
  function debounce(fn, delay = 300) {
    let timeoutId;
    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  }

  class LocalModal {
    constructor(element) {
      this.element = element;
      this.backdrop = null;
      this.previousFocus = null;
      modalInstances.set(element, this);
    }

    show() {
      if (!this.element) return;
      this.previousFocus = document.activeElement;
      const description = this.element.querySelector('.modal-body, [data-modal-description]');
      if (description) {
        description.id ||= `${this.element.id || 'modal'}Description`;
        this.element.setAttribute('aria-describedby', description.id);
      }
      this.element.classList.add('is-open');
      this.element.removeAttribute('aria-hidden');
      document.body.classList.add('modal-open');
      this.backdrop = document.createElement('div');
      this.backdrop.className = 'modal-backdrop';
      this.backdrop.addEventListener('click', () => this.hide());
      document.body.appendChild(this.backdrop);
      requestAnimationFrame(() => this.backdrop?.classList.add('is-visible'));
      this.getFocusableElements()[0]?.focus();
      this.element.addEventListener('keydown', this.handleKeydown);
    }

    hide() {
      if (!this.element) return;
      this.element.classList.remove('is-open');
      this.element.setAttribute('aria-hidden', 'true');
      this.backdrop?.remove();
      this.backdrop = null;
      document.body.classList.remove('modal-open');
      this.element.removeEventListener('keydown', this.handleKeydown);
      this.previousFocus?.focus?.();
      this.previousFocus = null;
    }

    handleKeydown = (event) => {
      if (event.key === 'Escape') this.hide();
      if (event.key !== 'Tab') return;
      const focusable = this.getFocusableElements();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    getFocusableElements() {
      return [...this.element.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')];
    }

    static getInstance(element) {
      return modalInstances.get(element) || null;
    }
  }

  window.bootstrap = window.bootstrap || { Modal: LocalModal };
  const closePhotoViewer = () => {
    const viewer = document.getElementById('photoViewer');
    if (!viewer) return;
    viewer.classList.remove('is-open');
    viewer.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('photo-viewer-open');
  };
  window.AppUI = {
    csrfHeaders() {
      const token = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
      return token ? { 'X-CSRFToken': token } : {};
    },
    toast(message, type = 'info') {
      const region = document.getElementById('toastRegion');
      if (!region) return;
      const toast = document.createElement('div');
      toast.className = `app-toast app-toast--${type}`;
      toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
      const icon = document.createElement('span');
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = type === 'error' ? '!' : type === 'success' ? 'OK' : 'i';
      const content = document.createElement('span');
      content.textContent = String(message);
      const close = document.createElement('button');
      close.type = 'button';
      close.setAttribute('aria-label', 'Cerrar notificación');
      close.textContent = 'x';
      toast.append(icon, content, close);
      close.addEventListener('click', () => toast.remove());
      region.appendChild(toast);
      window.setTimeout(() => toast.remove(), 5000);
    },
    confirm(message) {
      return new Promise((resolve) => {
        const previousFocus = document.activeElement;
        const dialog = document.createElement('div');
        dialog.className = 'app-confirm';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.innerHTML = `<div class="app-confirm__panel"><div class="app-confirm__mark">!</div><h2 id="appConfirmTitle">Confirma esta acción</h2><p id="appConfirmDescription"></p><div class="app-confirm__actions"><button type="button" class="btn-ios ghost" data-confirm-cancel>Cancelar</button><button type="button" class="btn-ios primary" data-confirm-ok>Continuar</button></div></div>`;
        dialog.setAttribute('aria-labelledby', 'appConfirmTitle');
        dialog.setAttribute('aria-describedby', 'appConfirmDescription');
        dialog.querySelector('p').textContent = message;
        const finish = (value) => { dialog.remove(); previousFocus?.focus?.(); resolve(value); };
        dialog.querySelector('[data-confirm-cancel]').addEventListener('click', () => finish(false));
        dialog.querySelector('[data-confirm-ok]').addEventListener('click', () => finish(true));
        dialog.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') finish(false);
          if (event.key !== 'Tab') return;
          const focusable = [...dialog.querySelectorAll('button:not([disabled])')];
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        document.body.appendChild(dialog);
        dialog.querySelector('[data-confirm-cancel]').focus();
      });
    },
    renderPagination(container, { total, page, pageSize, onPageChange, label = 'registros' }) {
      if (!container) return;
      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      container.replaceChildren();
      container.className = 'table-pagination';

      const info = document.createElement('span');
      info.className = 'table-pagination__info';
      info.textContent = `${total} ${label} · Página ${page} de ${totalPages}`;

      const controls = document.createElement('div');
      controls.className = 'table-pagination__controls';
      [['Anterior', page - 1, page <= 1], ['Siguiente', page + 1, page >= totalPages]].forEach(([text, nextPage, disabled]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn-ios secondary btn-sm';
        button.textContent = text;
        button.disabled = disabled;
        button.addEventListener('click', () => onPageChange(nextPage));
        controls.append(button);
      });

      container.append(info, controls);
    },
    rowActions(actions) {
      const container = document.createElement('div');
      container.className = 'table-row-actions';
      actions.forEach(({ label, icon, variant = 'ghost', onClick, disabled = false }) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `btn-ios ${variant} btn-sm table-row-actions__button`;
        button.title = label;
        button.setAttribute('aria-label', label);
        button.disabled = disabled;
        if (icon === 'id-card') button.innerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="8" cy="10" r="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5.5 16c.7-1.5 1.5-2.2 2.5-2.2s1.8.7 2.5 2.2M13 9h5M13 13h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
        else if (icon) button.innerHTML = `<svg class="icon" aria-hidden="true"><use href="/static/img/icons.svg#${icon}"></use></svg>`;
        else button.textContent = label;
        button.addEventListener('click', onClick);
        container.append(button);
      });
      return container;
    },
    openPhoto(src, name) {
      const viewer = document.getElementById('photoViewer');
      if (!viewer) return;
      viewer.querySelector('.photo-viewer__image').src = src || '/static/img/default-avatar.svg';
      viewer.querySelector('.photo-viewer__name').textContent = name || 'Empleado';
      viewer.classList.add('is-open');
      viewer.setAttribute('aria-hidden', 'false');
      document.body.classList.add('photo-viewer-open');
      viewer.querySelector('.photo-viewer__close')?.focus();
    },
  };

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('.employee-photo-trigger, #profileEmployeePhoto, #kioskPhoto');
    if (trigger) window.AppUI.openPhoto(trigger.dataset.photoSrc || trigger.src, trigger.dataset.photoName || trigger.alt);
    if (event.target.closest('.photo-viewer__close') || event.target.id === 'photoViewer') closePhotoViewer();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closePhotoViewer(); });

  const NotificationApp = {
    items: [],
    lastId: 0,
    unread: 0,
    initialized: false,
    pollTimer: null,
    init() {
      this.trigger = document.getElementById('notificationTrigger');
      this.panel = document.getElementById('notificationPanel');
      this.list = document.getElementById('notificationList');
      this.badge = document.getElementById('notificationBadge');
      this.readAll = document.getElementById('notificationReadAll');
      if (!this.trigger || !this.panel) return;
      this.trigger.addEventListener('click', () => this.toggle());
      this.readAll?.addEventListener('click', () => this.markRead());
      document.addEventListener('click', (event) => {
        if (!event.target.closest('.notification-menu')) this.close();
      });
      this.poll();
    },
    toggle() {
      const open = this.panel.classList.toggle('d-none') === false;
      this.trigger.setAttribute('aria-expanded', String(open));
    },
    close() {
      this.panel.classList.add('d-none');
      this.trigger.setAttribute('aria-expanded', 'false');
    },
    async poll() {
      try {
        const response = await fetch(`/api/notifications?after_id=${this.lastId}`, { cache: 'no-store' });
        if (!response.ok) return;
        const payload = await response.json();
        const fresh = Array.isArray(payload.items) ? payload.items : [];
        if (this.initialized && fresh.length) {
          fresh.forEach((item) => {
            window.AppUI.toast(`${item.titulo}: ${item.mensaje}`, item.prioridad === 'critica' ? 'error' : item.prioridad === 'advertencia' ? 'warning' : 'info');
          });
        }
        this.items = [...this.items, ...fresh].slice(-100);
        if (fresh.length) this.lastId = Math.max(this.lastId, ...fresh.map((item) => Number(item.id) || 0));
        if (payload.unread !== null && payload.unread !== undefined) this.unread = Number(payload.unread) || 0;
        else this.unread += fresh.filter((item) => !item.leida).length;
        this.render();
        this.initialized = true;
      } catch (error) {
        // The next poll retries transient connection failures.
      } finally {
        this.pollTimer = window.setTimeout(() => this.poll(), 60000);
      }
    },
    receive(item) {
      if (!item || Number(item.id) <= this.lastId) return;
      this.items = [...this.items, item].slice(-100);
      this.lastId = Number(item.id);
      if (!item.leida) this.unread += 1;
      window.AppUI.toast(`${item.titulo}: ${item.mensaje}`, item.prioridad === 'critica' ? 'error' : item.prioridad === 'advertencia' ? 'warning' : 'info');
      this.render();
    },
    render() {
      const unread = this.unread;
      this.badge.textContent = unread > 99 ? '99+' : String(unread);
      this.badge.classList.toggle('d-none', !unread);
      this.list.replaceChildren();
      if (!this.items.length) {
        this.list.innerHTML = '<p class="notification-empty">No hay notificaciones.</p>';
        return;
      }
      [...this.items].reverse().forEach((item) => {
        const article = document.createElement('article');
        article.className = `notification-item notification-item--${item.prioridad}${item.leida ? '' : ' is-unread'}`;
        article.innerHTML = `<div class="notification-item__top"><span class="notification-priority">${item.prioridad}</span><time>${new Date(item.creada_en).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time><button type="button" class="notification-dismiss" aria-label="Descartar notificación">x</button></div><strong></strong><p></p>`;
        article.querySelector('strong').textContent = item.titulo;
        article.querySelector('p').textContent = item.mensaje;
        article.querySelector('.notification-dismiss').addEventListener('click', () => this.discard(item.id));
        this.list.append(article);
      });
    },
    async markRead() {
      await fetch('/api/notifications/read', { method: 'PATCH', headers: window.AppUI.csrfHeaders() });
      this.items.forEach((item) => { item.leida = true; });
      this.unread = 0;
      this.render();
    },
    async discard(id) {
      await fetch(`/api/notifications/${id}`, { method: 'DELETE', headers: window.AppUI.csrfHeaders() });
      const discarded = this.items.find((item) => item.id === id);
      this.items = this.items.filter((item) => item.id !== id);
      if (discarded && !discarded.leida) this.unread = Math.max(0, this.unread - 1);
      this.render();
    },
  };

  const LiveUpdates = {
    source: null,
    wasDisconnected: false,
    reconnectTimer: null,
    reconnectDelay: 3000,
    start() {
      if (!window.WebSocket || this.source || this.reconnectTimer) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.source = new WebSocket(`${protocol}//${window.location.host}/api/ws`);
      this.source.onopen = () => {
        this.reconnectDelay = 3000;
        const reconnected = this.wasDisconnected;
        this.wasDisconnected = false;
        if (reconnected) window.dispatchEvent(new CustomEvent('app:live-reconnected'));
      };
      this.source.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type) window.dispatchEvent(new CustomEvent(`app:${message.type}`, { detail: message.payload }));
        } catch (error) {}
      };
      this.source.onerror = () => {
        this.wasDisconnected = true;
        window.dispatchEvent(new CustomEvent('app:live-disconnected'));
      };
      this.source.onclose = () => {
        this.source = null;
        this.reconnectTimer = window.setTimeout(() => {
          this.reconnectTimer = null;
          this.start();
        }, this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 60000);
      };
    },
    stop() {
      if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
      this.source?.close();
      this.source = null;
    },
  };

  document.addEventListener('click', (event) => {
    const dismiss = event.target.closest('[data-bs-dismiss="modal"]');
    if (dismiss) dismiss.closest('.modal') && window.bootstrap.Modal.getInstance(dismiss.closest('.modal'))?.hide();
  });

  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar-wide');
    const toggle = document.getElementById('sidebarToggle');
    const backdrop = document.getElementById('sidebarBackdrop');
    const setSidebarOpen = (open) => {
      sidebar?.classList.toggle('sidebar-open', open);
      document.body.classList.toggle('sidebar-is-open', open);
      toggle?.setAttribute('aria-expanded', String(open));
    };
    toggle?.setAttribute('aria-expanded', 'false');
    toggle?.addEventListener('click', () => setSidebarOpen(!sidebar?.classList.contains('sidebar-open')));
    backdrop?.addEventListener('click', () => setSidebarOpen(false));
    sidebar?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setSidebarOpen(false)));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') setSidebarOpen(false);
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) setSidebarOpen(false);
    });

    EmployeeApp.init();
    NotificationApp.init();
    LiveUpdates.start();
    window.addEventListener('app:notification', (event) => {
      NotificationApp.receive(event.detail);
      if (['empleado_registrado', 'empleado_estado_cambiado'].includes(event.detail?.tipo)) {
        EmployeeApp.fetchEmployees();
      }
    });
    window.addEventListener('app:employee_changed', () => EmployeeApp.fetchEmployees());
    window.addEventListener('app:organization_changed', () => EmployeeApp.ensureOrganizationCatalog(true));
    window.addEventListener('pagehide', () => {
      NotificationApp.pollTimer && window.clearTimeout(NotificationApp.pollTimer);
      LiveUpdates.stop();
    });
    window.addEventListener('pageshow', () => LiveUpdates.start());
  });

  const state = {
    q: '',
    page: 1,
    pageSize: 25,
    total: 0,
    loading: false,
  };

  const qs = (selector, scope = document) => scope.querySelector(selector);

  const EmployeeApp = {
    modal: null,
    form: null,
    list: null,
    emptyState: null,
    tableContainer: null,
    pagination: null,
    paginationInfo: null,
    loader: null,
    cardScanButton: null,
    cardScanFeedback: null,
    organizationCatalog: [],
    organizationCatalogPromise: null,

    getPhotoUrl(value) {
      const defaultAvatar = '/static/img/default-avatar.svg';
      const photoPath = String(value || '').trim();
      if (!photoPath) return defaultAvatar;
      if (/^\d+$/.test(photoPath)) return `/api/employees/${photoPath}/photo`;
      if (/^(https?:)?\/\//.test(photoPath) || photoPath.startsWith('/static/')) return photoPath;
      const normalizedPath = photoPath.replace(/^\/+/, '').split('/').map(encodeURIComponent).join('/');
      return `/static/${normalizedPath}`;
    },

    init() {
      this.modal = document.getElementById('employeeModal');
      this.form = document.getElementById('employeeForm');
      this.list = document.getElementById('employeesList');
      this.emptyState = document.getElementById('emptyStateRow');
      this.tableContainer = document.querySelector('.table-responsive');
      this.pagination = document.getElementById('pagination');
      this.paginationInfo = document.getElementById('paginationInfo');
      this.loader = document.getElementById('employeesLoader');
      this.cardScanButton = document.getElementById('scanCardBtn');
      this.cardScanFeedback = document.getElementById('scanCardFeedback');
      this.canManage = document.getElementById('employeesTable')?.dataset.canManage === 'true';
      this.isInspector = document.getElementById('employeesTable')?.dataset.role === 'Inspector';

      if (!this.list) return;

      if (this.form) this.bindEvents();
      this.populateFilterSelects();
      this.fetchEmployees();
      if (this.form) this.ensureOrganizationCatalog();
    },

    bindEvents() {
      this.cardScanButton?.addEventListener('click', () => this.scanCard());
      const newButton = document.getElementById('newBtn');
      newButton?.addEventListener('click', async () => {
        this.resetForm();
        await this.ensureOrganizationCatalog();
        this.setFormSelectsFromCatalog(this.organizationCatalog);
        this.openModal();
      });

      const viewOrganizationBtn = document.getElementById('viewOrganizationBtn');
      viewOrganizationBtn?.addEventListener('click', () => {
        window.location.href = '/organization';
      });

      document.querySelectorAll('[data-open-employee-modal]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          this.resetForm();
          await this.ensureOrganizationCatalog();
          this.setFormSelectsFromCatalog(this.organizationCatalog);
          this.openModal();
        });
      });

      this.form?.addEventListener('submit', (event) => this.handleSubmit(event));

      const searchInput = document.getElementById('searchInput');
      if (searchInput) {
        searchInput.addEventListener('input', debounce((event) => {
          state.q = event.target.value.trim();
          state.page = 1;
          this.fetchEmployees();
        }, 300));
      }

      const gerenciaFilter = document.getElementById('gerenciaFilter');
      const departamentoFilter = document.getElementById('departamentoFilter');
      const estadoFilter = document.getElementById('estadoFilter');
      const tipoNominaFilter = document.getElementById('tipoNominaFilter');
      const clearFiltersBtn = document.getElementById('clearFiltersBtn');

      [gerenciaFilter, departamentoFilter, estadoFilter, tipoNominaFilter].forEach((select) => {
        select?.addEventListener('change', () => {
          if (select === gerenciaFilter) {
            this.populateFilterSelects();
          }
          state.page = 1;
          this.fetchEmployees();
        });
      });

      clearFiltersBtn?.addEventListener('click', () => {
        state.q = '';
        if (searchInput) searchInput.value = '';
        if (gerenciaFilter) gerenciaFilter.value = '';
        if (departamentoFilter) departamentoFilter.value = '';
        if (estadoFilter) estadoFilter.value = '';
        if (tipoNominaFilter) tipoNominaFilter.value = '';
        state.page = 1;
        this.fetchEmployees();
      });
    },

    async scanCard() {
      const input = this.form?.querySelector('[name="codigo_tarjeta"]');
      if (!input || !this.cardScanButton) return;
      this.cardScanButton.disabled = true;
      input.value = '';
      input.placeholder = 'Leyendo...';
      if (this.cardScanFeedback) this.cardScanFeedback.textContent = 'Pase la tarjeta por el lector.';
      try {
        const response = await fetch('/api/rfid/read-card', {
          method: 'POST',
          headers: window.AppUI.csrfHeaders(),
          signal: AbortSignal.timeout(30000),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || 'No se pudo leer la tarjeta.');
        input.value = payload.codigo_tarjeta || '';
        input.placeholder = 'Código leído por el lector';
        if (this.cardScanFeedback) this.cardScanFeedback.textContent = 'Tarjeta leída correctamente.';
        input.focus();
      } catch (error) {
        input.placeholder = 'Código leído por el lector';
        if (this.cardScanFeedback) this.cardScanFeedback.textContent = error.name === 'TimeoutError' ? 'Tiempo de lectura agotado.' : error.message;
      } finally {
        this.cardScanButton.disabled = false;
      }
    },

    getModalInstance() {
      if (!this.modal || !window.bootstrap?.Modal) return null;
      return window.bootstrap.Modal.getInstance(this.modal) || new window.bootstrap.Modal(this.modal);
    },

    openModal() {
      const modal = this.getModalInstance();
      if (modal) modal.show();
    },

    closeModal() {
      const modal = this.getModalInstance();
      if (modal) modal.hide();
    },

    setLoading(on) {
      state.loading = !!on;
      if (this.loader) {
        this.loader.style.display = on ? 'block' : 'none';
      }
    },

    showError(message) {
      window.AppUI.toast(message, 'error');
    },

    escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[character]));
    },

    resetForm() {
      if (!this.form) return;

      this.form.reset();
      const hiddenFields = ['id', 'gerencia_id', 'departamento_id', 'cargo_id'];
      hiddenFields.forEach((fieldName) => {
        const field = this.form.querySelector(`[name="${fieldName}"]`);
        if (field) field.value = '';
      });

      const gerenciaSelect = this.form.querySelector('[name="gerencia"]');
      const departamentoSelect = this.form.querySelector('[name="departamento"]');
      const cargoSelect = this.form.querySelector('[name="cargo"]');

      if (gerenciaSelect) gerenciaSelect.value = '';
      if (departamentoSelect) {
        departamentoSelect.innerHTML = '<option value="">Seleccione un departamento</option>';
        departamentoSelect.disabled = true;
      }
      if (cargoSelect) {
        cargoSelect.innerHTML = '<option value="">Seleccione un cargo</option>';
        cargoSelect.disabled = true;
      }

      const modalTitle = document.getElementById('employeeModalLabel');
      if (modalTitle) modalTitle.textContent = 'Registrar empleado';
    },

    async handleSubmit(event) {
      event.preventDefault();
      const formData = new FormData(this.form);
      const id = this.form.querySelector('[name="id"]')?.value;
      const saveBtn = document.getElementById('saveBtn');
      const removePhoto = this.form.querySelector('[name="eliminar_foto"]');
      formData.set('eliminar_foto', removePhoto?.checked ? 'true' : 'false');

      try {
        if (saveBtn) saveBtn.disabled = true;
        const res = await fetch(id ? `/api/employees/${id}` : '/api/employees', {
          method: id ? 'PUT' : 'POST',
          headers: window.AppUI.csrfHeaders(),
          body: formData,
        });

        if (!res.ok) {
          const payload = await res.json().catch(() => ({}));
          throw new Error(payload.detail || 'Error guardando empleado.');
        }

        this.closeModal();
        this.fetchEmployees();
      } catch (error) {
        console.error(error);
        this.showError(error.message || 'No se pudo guardar el empleado. Revisa los datos e inténtalo de nuevo.');
      } finally {
        if (saveBtn) saveBtn.disabled = false;
      }
    },

    async fetchEmployees() {
      this.setLoading(true);
      try {
        const offset = (state.page - 1) * state.pageSize;
        const params = new URLSearchParams();
        const gerenciaFilter = document.getElementById('gerenciaFilter');
        const departamentoFilter = document.getElementById('departamentoFilter');
        const estadoFilter = document.getElementById('estadoFilter');
        const tipoNominaFilter = document.getElementById('tipoNominaFilter');

        if (state.q) params.set('q', state.q);
        if (estadoFilter?.value) params.set('estado', estadoFilter.value);
        if (tipoNominaFilter?.value) params.set('tipo_nomina', tipoNominaFilter.value);
        if (gerenciaFilter?.value) params.set('gerencia_id', gerenciaFilter.value);
        if (departamentoFilter?.value) params.set('departamento_id', departamentoFilter.value);
        params.set('limit', String(state.pageSize));
        params.set('offset', String(offset));

        const response = await fetch(`/api/employees?${params.toString()}`, { signal: AbortSignal.timeout(10000) });
        if (!response.ok) throw new Error(`Error ${response.status}`);

        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : (payload.items || []);
        state.total = Array.isArray(payload) ? payload.length : Number(payload.total) || items.length;

        if (payload.metrics) this.updateMetrics(payload.metrics);

        this.renderList(items);
        this.renderPagination();
      } catch (error) {
        console.error(error);
        this.updateMetrics({ active: '—', vacation: '—', retired_suspended: '—' });
        this.showError('Ocurrió un error al cargar empleados.');
      } finally {
        this.setLoading(false);
      }
    },

    updateMetrics(metrics) {
      if (!metrics) return;
      const map = {
        active: '#metric-active',
        vacation: '#metric-vacation',
        retired_suspended: '#metric-retired-suspended',
      };

      Object.entries(map).forEach(([key, selector]) => {
        if (metrics[key] !== undefined) {
          const element = qs(selector);
          if (element) element.textContent = metrics[key];
        }
      });

      const payrollFilter = document.getElementById('tipoNominaFilter');
      if (payrollFilter && Array.isArray(metrics.payroll_breakdown)) {
        const selected = payrollFilter.value;
        const payrolls = metrics.payroll_breakdown.map((item) => item.nombre).filter(Boolean);
        payrollFilter.innerHTML = '<option value="">Tipo de nómina</option>' + payrolls.map((payroll) => `<option value="${this.escapeHtml(payroll)}">${this.escapeHtml(payroll)}</option>`).join('');
        payrollFilter.value = payrolls.includes(selected) ? selected : '';
      }
    },

    getStatusBadgeClass(status) {
      const normalized = String(status || 'Activo').trim();
      const map = {
        Activo: 'badge-status--activo',
        Inactivo: 'badge-status--inactivo',
        Vacaciones: 'badge-status--vacaciones',
        Retirado: 'badge-status--retirado',
        Suspendido: 'badge-status--suspendido',
      };
      return map[normalized] || 'badge-status--activo';
    },

    renderList(items) {
      if (!this.list) return;
      this.list.innerHTML = '';

      if (!items || items.length === 0) {
        if (this.tableContainer) this.tableContainer.style.display = 'none';
        if (this.emptyState) this.emptyState.style.display = 'block';
        return;
      }

      if (this.tableContainer) this.tableContainer.style.display = 'block';
      if (this.emptyState) this.emptyState.style.display = 'none';

      items.forEach((employee) => {
        const row = document.createElement('tr');
        const statusClass = this.getStatusBadgeClass(employee.estado);

        row.innerHTML = this.isInspector ? `
          <td><span class="fw-medium">${this.escapeHtml(employee.nombre_apellido)}</span></td>
          <td><span class="employee-avatar-placeholder" aria-hidden="true">${this.escapeHtml((employee.nombre_apellido || '?').slice(0, 1).toUpperCase())}</span></td>
          <td><div>${this.escapeHtml(employee.gerencia || 'Sin gerencia')}</div><small class="text-muted">${this.escapeHtml(employee.departamento || 'Sin departamento')}</small></td>
          <td><span class="badge-pill ${statusClass}">${this.escapeHtml(employee.estado)}</span></td>
        ` : `
          <td>
            <div class="d-flex align-items-center gap-2">
              <button type="button" class="employee-photo-trigger" data-photo-src="${this.escapeHtml(this.getPhotoUrl(employee.foto_url))}" data-photo-name="${this.escapeHtml(employee.nombre_apellido)}" aria-label="Ampliar foto de ${this.escapeHtml(employee.nombre_apellido)}"><img class="employee-avatar" src="${this.getPhotoUrl(employee.foto_url)}" alt=""></button>
              <span class="fw-medium">${this.escapeHtml(employee.nombre_apellido)}</span>
            </div>
          </td>
          <td>${this.escapeHtml(employee.cedula)}</td>
          <td>
            <div>${this.escapeHtml(employee.gerencia)}</div>
            <small class="text-muted">${this.escapeHtml(employee.departamento)}</small>
          </td>
          <td>${this.escapeHtml(employee.cargo)}</td>
          <td>
            <span class="badge-pill ${statusClass}">
              ${this.escapeHtml(employee.estado)}
            </span>
          </td>
          <td class="text-end"><div data-row-actions></div></td>
        `;

        const actions = [{ label: 'Ver ficha del empleado', icon: 'id-card', variant: 'ghost', onClick: () => this.viewProfile(employee.id) }];
        if (this.isInspector) return this.list.appendChild(row);
        if (this.canManage) {
          actions.push({ label: 'Editar empleado', icon: 'edit', variant: 'ghost', onClick: () => this.editEmployee(employee.id) });
          actions.push({ label: 'Inhabilitar empleado', icon: 'trash', variant: 'danger', onClick: () => this.disableEmployee(employee.id) });
        }
        row.querySelector('[data-row-actions]').replaceWith(window.AppUI.rowActions(actions));
        row.querySelector('.employee-avatar')?.addEventListener('error', (event) => {
          event.currentTarget.src = this.getPhotoUrl(null);
        }, { once: true });
        this.list.appendChild(row);
      });
    },

    renderPagination() {
      if (!this.pagination) return;
      window.AppUI.renderPagination(this.pagination, {
        total: state.total,
        page: state.page,
        pageSize: state.pageSize,
        onPageChange: (nextPage) => {
          state.page = nextPage;
          this.fetchEmployees();
        },
      });
    },

    async ensureOrganizationCatalog(force = false) {
      if (!force && this.organizationCatalog.length) return this.organizationCatalog;
      if (!force && this.organizationCatalogPromise) return this.organizationCatalogPromise;

      this.organizationCatalogPromise = fetch('/api/organization')
        .then(async (response) => {
          if (!response.ok) throw new Error(`Error ${response.status}`);
          const catalog = await response.json();
          this.organizationCatalog = Array.isArray(catalog) ? catalog : [];
          this.populateFilterSelects();
          return this.organizationCatalog;
        })
        .catch((error) => {
          console.error('No se pudo cargar la organización', error);
          this.organizationCatalog = [];
          this.populateFilterSelects();
          return [];
        })
        .finally(() => {
          this.organizationCatalogPromise = null;
        });

      return this.organizationCatalogPromise;
    },

    populateFilterSelects() {
      const gerenciaFilter = document.getElementById('gerenciaFilter');
      const departamentoFilter = document.getElementById('departamentoFilter');
      if (!gerenciaFilter || !departamentoFilter) return;

      const selectedGerencia = gerenciaFilter.value;
      const selectedDepartamento = departamentoFilter.value;

      const gerencias = (this.organizationCatalog || []).filter((g) => (g.estado || 'Activo') === 'Activo');
      gerenciaFilter.innerHTML = '<option value="">Gerencia</option>' + gerencias.map((g) => `<option value="${g.id}">${this.escapeHtml(g.nombre)}</option>`).join('');

      gerenciaFilter.value = gerencias.some((g) => String(g.id) === selectedGerencia) ? selectedGerencia : '';

      const departments = selectedGerencia && gerencias.some((g) => String(g.id) === selectedGerencia)
        ? (gerencias.find((g) => String(g.id) === selectedGerencia)?.departamentos || []).filter((d) => (d.estado || 'Activo') === 'Activo')
        : gerencias.flatMap((g) => (g.departamentos || []).filter((d) => (d.estado || 'Activo') === 'Activo'));

      departamentoFilter.innerHTML = '<option value="">Departamento</option>' + departments.map((d) => `<option value="${d.id}">${this.escapeHtml(d.nombre)}</option>`).join('');
      departamentoFilter.value = departments.some((d) => String(d.id) === selectedDepartamento) ? selectedDepartamento : '';
    },

    setFormSelectsFromCatalog(catalog) {
      if (!this.form || !catalog) return;

      const gerenciaSelect = this.form.querySelector('[name="gerencia"]');
      const departamentoSelect = this.form.querySelector('[name="departamento"]');
      const cargoSelect = this.form.querySelector('[name="cargo"]');

      if (!gerenciaSelect || !departamentoSelect || !cargoSelect) return;

      const activeCatalog = catalog.filter((g) => (g.estado || 'Activo') === 'Activo');
      const buildOptions = (items, placeholder) => [
        `<option value="">${placeholder}</option>`,
        ...items.map((item) => `<option value="${item.nombre}">${item.nombre}</option>`),
      ].join('');

      gerenciaSelect.innerHTML = buildOptions(activeCatalog, 'Seleccione una gerencia');
      gerenciaSelect.disabled = false;
      departamentoSelect.innerHTML = '<option value="">Seleccione un departamento</option>';
      departamentoSelect.disabled = true;
      cargoSelect.innerHTML = '<option value="">Seleccione un cargo</option>';
      cargoSelect.disabled = true;

      gerenciaSelect.onchange = () => {
        const selectedGerencia = activeCatalog.find((item) => item.nombre === gerenciaSelect.value);
        const departamentos = selectedGerencia ? (selectedGerencia.departamentos || []).filter((d) => (d.estado || 'Activo') === 'Activo') : [];
        
        const gId = this.form.querySelector('[name="gerencia_id"]');
        const dId = this.form.querySelector('[name="departamento_id"]');
        const cId = this.form.querySelector('[name="cargo_id"]');

        if (gId) gId.value = selectedGerencia?.id || '';
        if (dId) dId.value = '';
        if (cId) cId.value = '';

        departamentoSelect.innerHTML = buildOptions(departamentos, 'Seleccione un departamento');
        departamentoSelect.disabled = !departamentos.length;
        cargoSelect.innerHTML = '<option value="">Seleccione un cargo</option>';
        cargoSelect.disabled = true;
      };

      departamentoSelect.onchange = () => {
        const selectedGerencia = activeCatalog.find((item) => item.nombre === gerenciaSelect.value);
        const selectedDepartamento = (selectedGerencia?.departamentos || []).find((d) => d.nombre === departamentoSelect.value);
        const cargos = selectedDepartamento ? (selectedDepartamento.cargos || []).filter((c) => (c.estado || 'Activo') === 'Activo') : [];
        
        const dId = this.form.querySelector('[name="departamento_id"]');
        const cId = this.form.querySelector('[name="cargo_id"]');

        if (dId) dId.value = selectedDepartamento?.id || '';
        if (cId) cId.value = '';

        cargoSelect.innerHTML = buildOptions(cargos, 'Seleccione un cargo');
        cargoSelect.disabled = !cargos.length;
      };

      cargoSelect.onchange = () => {
        const selectedGerencia = activeCatalog.find((item) => item.nombre === gerenciaSelect.value);
        const selectedDepartamento = (selectedGerencia?.departamentos || []).find((d) => d.nombre === departamentoSelect.value);
        const selectedCargo = (selectedDepartamento?.cargos || []).find((c) => c.nombre === cargoSelect.value);
        
        const cId = this.form.querySelector('[name="cargo_id"]');
        if (cId) cId.value = selectedCargo?.id || '';
      };
    },

    async editEmployee(employeeId) {
      try {
        const catalog = await this.ensureOrganizationCatalog();
        this.setFormSelectsFromCatalog(catalog);

        const response = await fetch(`/api/employees/${employeeId}`);
        if (!response.ok) throw new Error('No se pudo cargar el empleado');
        const employee = await response.json();

        this.form.reset();
        this.form.querySelector('[name="id"]').value = employee.id;
        this.form.querySelector('[name="cedula"]').value = employee.cedula || '';
        this.form.querySelector('[name="codigo_tarjeta"]').value = employee.codigo_tarjeta || '';
        this.form.querySelector('[name="nombre_apellido"]').value = employee.nombre_apellido || '';
        this.form.querySelector('[name="fecha_nacimiento"]').value = employee.fecha_nacimiento || '';
        this.form.querySelector('[name="telefono"]').value = employee.telefono || '';
        this.form.querySelector('[name="email"]').value = employee.email || '';
        this.form.querySelector('[name="contacto_emergencia_parentesco"]').value = employee.contacto_emergencia_parentesco || '';
        this.form.querySelector('[name="contacto_emergencia_telefono"]').value = employee.contacto_emergencia_telefono || '';
        this.form.querySelector('[name="estado"]').value = employee.estado || 'Activo';
        this.form.querySelector('[name="tipo_nomina"]').value = employee.tipo_nomina || '';

        const gerenciaSelect = this.form.querySelector('[name="gerencia"]');
        const departamentoSelect = this.form.querySelector('[name="departamento"]');
        const cargoSelect = this.form.querySelector('[name="cargo"]');

        const activeCatalog = catalog.filter((g) => (g.estado || 'Activo') === 'Activo');
        const matchedGerencia = activeCatalog.find((g) => g.nombre === employee.gerencia || Number(g.id) === Number(employee.gerencia_id));
        
        if (matchedGerencia && gerenciaSelect) {
          gerenciaSelect.value = matchedGerencia.nombre;
          gerenciaSelect.dispatchEvent(new Event('change'));
        }

        const departamentos = matchedGerencia ? (matchedGerencia.departamentos || []).filter((d) => (d.estado || 'Activo') === 'Activo') : [];
        const matchedDepartamento = departamentos.find((d) => d.nombre === employee.departamento || Number(d.id) === Number(employee.departamento_id));
        
        if (matchedDepartamento && departamentoSelect) {
          departamentoSelect.value = matchedDepartamento.nombre;
          departamentoSelect.dispatchEvent(new Event('change'));
        }

        const cargos = matchedDepartamento ? (matchedDepartamento.cargos || []).filter((c) => (c.estado || 'Activo') === 'Activo') : [];
        const matchedCargo = cargos.find((c) => c.nombre === employee.cargo || Number(c.id) === Number(employee.cargo_id));
        
        if (matchedCargo && cargoSelect) {
          cargoSelect.value = matchedCargo.nombre;
          cargoSelect.dispatchEvent(new Event('change'));
        }

        const modalTitle = document.getElementById('employeeModalLabel');
        if (modalTitle) modalTitle.textContent = 'Editar empleado';
        this.openModal();
      } catch (error) {
        console.error(error);
        this.showError('No se pudo cargar empleado.');
      }
    },

    async disableEmployee(employeeId) {
      const ok = await window.AppUI.confirm('¿Está seguro de que desea inhabilitar a este empleado?');
      if (!ok) return;

      try {
        const response = await fetch(`/api/employees/${employeeId}`, {
          method: 'DELETE',
          headers: window.AppUI.csrfHeaders(),
        });
        if (!response.ok) throw new Error('No se pudo inhabilitar al empleado');
        window.AppUI.toast('Empleado inhabilitado con éxito', 'success');
        this.fetchEmployees();
      } catch (error) {
        console.error(error);
        this.showError(error.message);
      }
    },

    async viewProfile(employeeId) {
      const modal = document.getElementById('employeeProfileModal');
      const errorElement = document.getElementById('employeeProfileError');
      const loadProfile = async () => {
      try {
        const response = await fetch(`/api/employees/${employeeId}`);
        if (!response.ok) throw new Error('No se pudo cargar la información del empleado.');
        const employee = await response.json();

        document.getElementById('profileEmployeeName').textContent = employee.nombre_apellido || '--';
        document.getElementById('profileEmployeeOrg').textContent = [employee.gerencia, employee.departamento, employee.cargo].filter(Boolean).join(' / ') || '--';
        document.getElementById('profileEmployeePhoto').src = this.getPhotoUrl(employee.foto_url);
        document.getElementById('profilePersonalData').innerHTML = [
          ['Cédula', employee.cedula],
          ['Código de tarjeta', employee.codigo_tarjeta],
          ['Estado', employee.estado],
          ['Tipo de nómina', employee.tipo_nomina],
          ['Fecha de nacimiento', employee.fecha_nacimiento],
        ].map(([label, value]) => `<div><span>${label}</span><strong>${this.escapeHtml(value || '--')}</strong></div>`).join('');
        document.getElementById('profileContactData').innerHTML = [
          ['Teléfono', employee.telefono],
          ['Correo electrónico', employee.email],
          ['Parentesco de emergencia', employee.contacto_emergencia_parentesco],
          ['Teléfono de emergencia', employee.contacto_emergencia_telefono],
        ].map(([label, value]) => `<div><span>${label}</span><strong>${this.escapeHtml(value || '--')}</strong></div>`).join('');
        errorElement?.classList.add('d-none');
      } catch (error) {
        console.error(error);
        if (errorElement) {
          errorElement.textContent = error.message;
          errorElement.classList.remove('d-none');
        }
      }
      };

      await loadProfile();
      if (modal && window.bootstrap?.Modal) {
        const profileModal = window.bootstrap.Modal.getInstance(modal) || new window.bootstrap.Modal(modal);
        profileModal.show();
      }
    }
  };
})();