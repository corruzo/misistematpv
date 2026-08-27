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
      modalInstances.set(element, this);
    }

    show() {
      if (!this.element) return;
      this.element.classList.add('is-open');
      this.element.removeAttribute('aria-hidden');
      document.body.classList.add('modal-open');
      this.backdrop = document.createElement('div');
      this.backdrop.className = 'modal-backdrop';
      this.backdrop.addEventListener('click', () => this.hide());
      document.body.appendChild(this.backdrop);
      requestAnimationFrame(() => this.backdrop?.classList.add('is-visible'));
      this.element.querySelector('[autofocus], .btn-close')?.focus();
    }

    hide() {
      if (!this.element) return;
      this.element.classList.remove('is-open');
      this.element.setAttribute('aria-hidden', 'true');
      this.backdrop?.remove();
      this.backdrop = null;
      document.body.classList.remove('modal-open');
    }

    static getInstance(element) {
      return modalInstances.get(element) || null;
    }
  }

  window.bootstrap = window.bootstrap || { Modal: LocalModal };
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
        const dialog = document.createElement('div');
        dialog.className = 'app-confirm';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.innerHTML = `<div class="app-confirm__panel"><div class="app-confirm__mark">!</div><h2>Confirma esta acción</h2><p></p><div class="app-confirm__actions"><button type="button" class="btn-ios ghost" data-confirm-cancel>Cancelar</button><button type="button" class="btn-ios primary" data-confirm-ok>Continuar</button></div></div>`;
        dialog.querySelector('p').textContent = message;
        const finish = (value) => { dialog.remove(); resolve(value); };
        dialog.querySelector('[data-confirm-cancel]').addEventListener('click', () => finish(false));
        dialog.querySelector('[data-confirm-ok]').addEventListener('click', () => finish(true));
        dialog.addEventListener('keydown', (event) => { if (event.key === 'Escape') finish(false); });
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
  };

  const NotificationApp = {
    items: [],
    lastId: 0,
    unread: 0,
    initialized: false,
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
        window.setTimeout(() => this.poll(), 60000);
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
    start() {
      if (!window.EventSource) return;
      const source = new EventSource('/api/live');
      ['attendance', 'access_denied', 'notification'].forEach((eventType) => {
        source.addEventListener(eventType, (event) => {
          try { window.dispatchEvent(new CustomEvent(`app:${eventType}`, { detail: JSON.parse(event.data) })); } catch (error) {}
        });
      });
      source.onerror = () => {};
    },
  };

  document.addEventListener('click', (event) => {
    const dismiss = event.target.closest('[data-bs-dismiss="modal"]');
    if (dismiss) dismiss.closest('.modal') && window.bootstrap.Modal.getInstance(dismiss.closest('.modal'))?.hide();
    const toggle = event.target.closest('[data-bs-toggle="collapse"]');
    if (toggle) {
      const target = document.querySelector(toggle.dataset.bsTarget);
      target?.classList.toggle('show');
      toggle.setAttribute('aria-expanded', String(target?.classList.contains('show')));
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar-wide');
    const toggle = document.getElementById('sidebarToggle');
    toggle?.addEventListener('click', () => sidebar?.classList.toggle('sidebar-open'));
    sidebar?.addEventListener('click', (event) => {
      if (event.target === sidebar) sidebar.classList.remove('sidebar-open');
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') sidebar?.classList.remove('sidebar-open');
    });

    EmployeeApp.init();
    NotificationApp.init();
    LiveUpdates.start();
    window.addEventListener('app:notification', (event) => NotificationApp.receive(event.detail));
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
    organizationCatalog: [],
    organizationCatalogPromise: null,

    init() {
      this.modal = document.getElementById('employeeModal');
      this.form = document.getElementById('employeeForm');
      this.list = document.getElementById('employeesList');
      this.emptyState = document.getElementById('emptyStateRow');
      this.tableContainer = document.querySelector('.table-responsive');
      this.pagination = document.getElementById('pagination');
      this.paginationInfo = document.getElementById('paginationInfo');
      this.loader = document.getElementById('employeesLoader');
      this.canManage = document.getElementById('employeesTable')?.dataset.canManage === 'true';

      if (!this.form || !this.list) return;

      this.bindEvents();
      this.ensureOrganizationCatalog().finally(() => {
        this.populateFilterSelects();
        this.fetchEmployees();
      });
    },

    bindEvents() {
      const newButton = document.getElementById('newBtn');
      newButton?.addEventListener('click', async () => {
        this.resetForm();
        await this.ensureOrganizationCatalog();
        this.setFormSelectsFromCatalog(this.organizationCatalog);
        this.openModal();
      });

      const viewStructureBtn = document.getElementById('viewStructureBtn');
      viewStructureBtn?.addEventListener('click', () => {
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

      this.form.addEventListener('submit', (event) => this.handleSubmit(event));

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

        const response = await fetch(`/api/employees?${params.toString()}`);
        if (!response.ok) throw new Error(`Error ${response.status}`);

        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : (payload.items || []);
        state.total = Array.isArray(payload) ? payload.length : Number(payload.total) || items.length;

        if (payload.metrics) this.updateMetrics(payload.metrics);

        this.renderList(items);
        this.renderPagination();
      } catch (error) {
        console.error(error);
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

      const defaultAvatar = '/static/img/default-avatar.svg';

      items.forEach((employee) => {
        const row = document.createElement('tr');
        const fotoSrc = employee.foto_url ? `/static/${employee.foto_url}` : defaultAvatar;
        const statusClass = this.getStatusBadgeClass(employee.estado);

        row.innerHTML = `
          <td>
            <div class="d-flex align-items-center gap-2">
              <img class="employee-avatar" src="${fotoSrc}" alt="avatar" />
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
        if (this.canManage) {
          actions.push({ label: 'Editar empleado', icon: 'edit', variant: 'ghost', onClick: () => this.editEmployee(employee.id) });
          actions.push({ label: 'Inhabilitar empleado', icon: 'trash', variant: 'danger', onClick: () => this.disableEmployee(employee.id) });
        }
        row.querySelector('[data-row-actions]').replaceWith(window.AppUI.rowActions(actions));
        row.querySelector('.employee-avatar')?.addEventListener('error', (event) => {
          event.currentTarget.src = defaultAvatar;
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
        document.getElementById('profileEmployeePhoto').src = employee.foto_url || '/static/img/default-avatar.svg';
        document.getElementById('profilePersonalData').innerHTML = [
          ['Cédula', employee.cedula],
          ['Código RFID', employee.codigo_tarjeta],
          ['Estado', employee.estado],
          ['Tipo de nómina', employee.tipo_nomina],
          ['Fecha de nacimiento', employee.fecha_nacimiento],
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