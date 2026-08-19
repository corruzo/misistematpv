(() => {
  const state = {
    q: '',
    page: 1,
    pageSize: 10,
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

      if (!this.form || !this.list) {
        return;
      }

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
      const clearFiltersBtn = document.getElementById('clearFiltersBtn');

      [gerenciaFilter, departamentoFilter, estadoFilter].forEach((select) => {
        select?.addEventListener('change', () => {
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
        state.page = 1;
        this.fetchEmployees();
      });
    },

    getModalInstance() {
      if (!this.modal || typeof bootstrap === 'undefined' || !bootstrap.Modal) {
        return null;
      }

      try {
        return bootstrap.Modal.getInstance(this.modal) || new bootstrap.Modal(this.modal);
      } catch (err) {
        console.warn('Bootstrap Modal aún no está listo:', err);
        return null;
      }
    },

    openModal() {
      const modal = this.getModalInstance();
      if (modal) {
        modal.show();
        return;
      }

      setTimeout(() => {
        const retryModal = this.getModalInstance();
        if (retryModal) retryModal.show();
      }, 150);
    },

    closeModal() {
      const modal = this.getModalInstance();
      if (modal) {
        modal.hide();
        return;
      }

      setTimeout(() => {
        const retryModal = this.getModalInstance();
        if (retryModal) retryModal.hide();
      }, 150);
    },

    setLoading(on) {
      state.loading = !!on;
      if (this.loader) {
        this.loader.style.display = on ? 'block' : 'none';
      }
    },

    showError(message) {
      alert(message);
    },

    escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (character) => ({
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

      try {
        if (saveBtn) saveBtn.disabled = true;
        const res = await fetch(id ? `/api/employees/${id}` : '/api/employees', {
          method: id ? 'PUT' : 'POST',
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
        this.showError(error.message || 'Error guardando empleado.');
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

        if (state.q) params.set('q', state.q);
        if (estadoFilter && estadoFilter.value) {
          params.set('estado', estadoFilter.value);
        }
        if (gerenciaFilter && gerenciaFilter.value) {
          params.set('gerencia', gerenciaFilter.value);
        }
        if (departamentoFilter && departamentoFilter.value) {
          params.set('departamento', departamentoFilter.value);
        }
        params.set('limit', String(state.pageSize));
        params.set('offset', String(offset));

        const response = await fetch(`/api/employees?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`Error ${response.status}`);
        }

        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : (payload.items || []);
        state.total = Array.isArray(payload) ? payload.length : Number(payload.total) || items.length;

        if (payload.metrics) {
          this.updateMetrics(payload.metrics);
        }

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
        total: '#metric-total',
        active: '#metric-active',
        depts: '#metric-depts',
        types: '#metric-types',
      };

      Object.entries(map).forEach(([key, selector]) => {
        if (metrics[key] !== undefined) {
          const element = qs(selector);
          if (element) element.textContent = metrics[key];
        }
      });
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
              <img class="employee-avatar" src="${fotoSrc}" onerror="this.onerror=null; this.src='${defaultAvatar}';" alt="avatar" />
              <span class="fw-medium">${this.escapeHtml(employee.nombre_apellido || '')}</span>
            </div>
          </td>
          <td>${this.escapeHtml(employee.cedula || '')}</td>
          <td>
            <div>${this.escapeHtml(employee.gerencia || '')}</div>
            <small class="text-muted">${this.escapeHtml(employee.departamento || '')}</small>
          </td>
          <td>${this.escapeHtml(employee.cargo || '')}</td>
          <td>
            <span class="badge-pill ${statusClass}">
              ${this.escapeHtml(employee.estado || '')}
            </span>
          </td>
          <td class="text-end">
            <div class="btn-group btn-group-sm">
              <button type="button" class="btn-ios secondary btn-sm" data-action="edit" data-id="${employee.id}">Editar</button>
              <button type="button" class="btn-ios secondary btn-sm text-danger" data-action="disable" data-id="${employee.id}">Inhabilitar</button>
            </div>
          </td>
        `;

        row.querySelector('[data-action="edit"]')?.addEventListener('click', () => this.editEmployee(employee.id));
        row.querySelector('[data-action="disable"]')?.addEventListener('click', () => this.disableEmployee(employee.id));
        this.list.appendChild(row);
      });
    },

    renderPagination() {
      if (!this.pagination) return;

      const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
      this.pagination.innerHTML = '';

      const prevButton = document.createElement('button');
      prevButton.type = 'button';
      prevButton.textContent = 'Anterior';
      prevButton.className = 'btn-ios secondary btn-sm';
      prevButton.disabled = state.page <= 1;
      prevButton.addEventListener('click', () => {
        if (state.page > 1) {
          state.page -= 1;
          this.fetchEmployees();
        }
      });

      const nextButton = document.createElement('button');
      nextButton.type = 'button';
      nextButton.textContent = 'Siguiente';
      nextButton.className = 'btn-ios secondary btn-sm';
      nextButton.disabled = state.page >= totalPages;
      nextButton.addEventListener('click', () => {
        if (state.page < totalPages) {
          state.page += 1;
          this.fetchEmployees();
        }
      });

      const info = document.createElement('div');
      info.className = 'small text-muted align-self-center px-2';
      info.textContent = `Página ${state.page} de ${totalPages}`;

      this.pagination.append(prevButton, info, nextButton);

      if (this.paginationInfo) {
        this.paginationInfo.textContent = `${state.total} registros`;
      }
    },

    async ensureOrganizationCatalog(force = false) {
      if (!force && this.organizationCatalog.length) {
        return this.organizationCatalog;
      }

      if (!force && this.organizationCatalogPromise) {
        return this.organizationCatalogPromise;
      }

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

      const gerencias = (this.organizationCatalog || []).filter((gerencia) => (gerencia.estado || 'Activo') === 'Activo');
      gerenciaFilter.innerHTML = '<option value="">Gerencia</option>' + gerencias.map((gerencia) => `<option value="${this.escapeHtml(gerencia.nombre)}">${this.escapeHtml(gerencia.nombre)}</option>`).join('');

      if (selectedGerencia && gerencias.some((gerencia) => gerencia.nombre === selectedGerencia)) {
        gerenciaFilter.value = selectedGerencia;
      } else {
        gerenciaFilter.value = '';
      }

      const departments = selectedGerencia && gerencias.some((gerencia) => gerencia.nombre === selectedGerencia)
        ? (gerencias.find((gerencia) => gerencia.nombre === selectedGerencia)?.departamentos || []).filter((departamento) => (departamento.estado || 'Activo') === 'Activo')
        : gerencias.flatMap((gerencia) => (gerencia.departamentos || []).filter((departamento) => (departamento.estado || 'Activo') === 'Activo'));

      departamentoFilter.innerHTML = '<option value="">Departamento</option>' + departments.map((departamento) => `<option value="${this.escapeHtml(departamento.nombre)}">${this.escapeHtml(departamento.nombre)}</option>`).join('');

      if (selectedDepartamento && departments.some((departamento) => departamento.nombre === selectedDepartamento)) {
        departamentoFilter.value = selectedDepartamento;
      } else {
        departamentoFilter.value = '';
      }

      if (!selectedGerencia && !selectedDepartamento) {
        departamentoFilter.value = '';
      }
    },

    setFormSelectsFromCatalog(catalog) {
      if (!this.form || !catalog) return;

      const gerenciaSelect = this.form.querySelector('[name="gerencia"]');
      const departamentoSelect = this.form.querySelector('[name="departamento"]');
      const cargoSelect = this.form.querySelector('[name="cargo"]');

      if (!gerenciaSelect || !departamentoSelect || !cargoSelect) return;

      const activeCatalog = (catalog || []).filter((gerencia) => (gerencia.estado || 'Activo') === 'Activo');
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
        const selectedName = gerenciaSelect.value;
        const selectedGerencia = activeCatalog.find((item) => item.nombre === selectedName);
        const departamentos = selectedGerencia ? (selectedGerencia.departamentos || []).filter((departamento) => (departamento.estado || 'Activo') === 'Activo') : [];
        const gerenciaIdInput = this.form.querySelector('[name="gerencia_id"]');
        const departamentoIdInput = this.form.querySelector('[name="departamento_id"]');
        const cargoIdInput = this.form.querySelector('[name="cargo_id"]');

        if (gerenciaIdInput) gerenciaIdInput.value = selectedGerencia ? selectedGerencia.id : '';
        if (departamentoIdInput) departamentoIdInput.value = '';
        if (cargoIdInput) cargoIdInput.value = '';

        departamentoSelect.innerHTML = [
          '<option value="">Seleccione un departamento</option>',
          ...(departamentos || []).map((departamento) => `<option value="${departamento.nombre}">${departamento.nombre}</option>`),
        ].join('');
        departamentoSelect.disabled = !(departamentos && departamentos.length);
        cargoSelect.innerHTML = '<option value="">Seleccione un cargo</option>';
        cargoSelect.disabled = true;
      };

      departamentoSelect.onchange = () => {
        const selectedGerenciaName = gerenciaSelect.value;
        const selectedGerencia = activeCatalog.find((item) => item.nombre === selectedGerenciaName) || { departamentos: [] };
        const selectedNombre = departamentoSelect.value;
        const selectedDepartamento = (selectedGerencia.departamentos || []).find((item) => item.nombre === selectedNombre);
        const cargos = selectedDepartamento ? (selectedDepartamento.cargos || []).filter((cargo) => (cargo.estado || 'Activo') === 'Activo') : [];
        const departamentoIdInput = this.form.querySelector('[name="departamento_id"]');
        const cargoIdInput = this.form.querySelector('[name="cargo_id"]');

        if (departamentoIdInput) departamentoIdInput.value = selectedDepartamento ? selectedDepartamento.id : '';
        if (cargoIdInput) cargoIdInput.value = '';

        cargoSelect.innerHTML = [
          '<option value="">Seleccione un cargo</option>',
          ...(cargos || []).map((cargo) => `<option value="${cargo.nombre}">${cargo.nombre}</option>`),
        ].join('');
        cargoSelect.disabled = !(cargos && cargos.length);
      };

      cargoSelect.onchange = () => {
        const selectedGerenciaName = gerenciaSelect.value;
        const selectedGerencia = activeCatalog.find((item) => item.nombre === selectedGerenciaName) || { departamentos: [] };
        const selectedDepartamentoName = departamentoSelect.value;
        const selectedDepartamento = (selectedGerencia.departamentos || []).find((item) => item.nombre === selectedDepartamentoName) || { cargos: [] };
        const selectedCargo = ((selectedDepartamento.cargos || []).filter((cargo) => (cargo.estado || 'Activo') === 'Activo')).find((item) => item.nombre === cargoSelect.value);
        const cargoIdInput = this.form.querySelector('[name="cargo_id"]');
        if (cargoIdInput) cargoIdInput.value = selectedCargo ? selectedCargo.id : '';
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
        this.form.querySelector('[name="nombre_apellido"]').value = employee.nombre_apellido || '';
        this.form.querySelector('[name="estado"]').value = employee.estado || 'Activo';
        this.form.querySelector('[name="tipo_nomina"]').value = employee.tipo_nomina || '';

        const gerenciaSelect = this.form.querySelector('[name="gerencia"]');
        const departamentoSelect = this.form.querySelector('[name="departamento"]');
        const cargoSelect = this.form.querySelector('[name="cargo"]');

        const activeCatalog = (catalog || []).filter((gerencia) => (gerencia.estado || 'Activo') === 'Activo');
        const matchedGerencia = activeCatalog.find((item) => item.nombre === employee.gerencia || Number(item.id) === Number(employee.gerencia_id));
        const gerenciaIdInput = this.form.querySelector('[name="gerencia_id"]');
        if (matchedGerencia && gerenciaSelect) {
          gerenciaSelect.value = matchedGerencia.nombre;
          if (gerenciaIdInput) gerenciaIdInput.value = matchedGerencia.id;
        } else if (gerenciaSelect && (employee.gerencia || employee.gerencia_id)) {
          const legacyGerenciaName = employee.gerencia || `Gerencia ${employee.gerencia_id || ''}`;
          gerenciaSelect.innerHTML = [
            '<option value="">Seleccione una gerencia</option>',
            `<option value="${legacyGerenciaName}" selected>${legacyGerenciaName} (inactivo)</option>`,
          ].join('');
          gerenciaSelect.disabled = true;
          if (gerenciaIdInput) gerenciaIdInput.value = employee.gerencia_id || '';
        }

        const departamentos = matchedGerencia ? (matchedGerencia.departamentos || []).filter((item) => (item.estado || 'Activo') === 'Activo') : [];
        if (departamentoSelect) {
          if (matchedGerencia) {
            departamentoSelect.innerHTML = [
              '<option value="">Seleccione un departamento</option>',
              ...departamentos.map((item) => `<option value="${item.nombre}">${item.nombre}</option>`),
            ].join('');
            departamentoSelect.disabled = !departamentos.length;
          } else if (employee.departamento || employee.departamento_id) {
            const legacyDepartamentoName = employee.departamento || `Departamento ${employee.departamento_id || ''}`;
            departamentoSelect.innerHTML = [
              '<option value="">Seleccione un departamento</option>',
              `<option value="${legacyDepartamentoName}" selected>${legacyDepartamentoName} (inactivo)</option>`,
            ].join('');
            departamentoSelect.disabled = true;
          }
        }

        const matchedDepartamento = departamentos.find((item) => item.nombre === employee.departamento || Number(item.id) === Number(employee.departamento_id));
        const departamentoIdInput = this.form.querySelector('[name="departamento_id"]');
        if (matchedDepartamento && departamentoSelect) {
          departamentoSelect.value = matchedDepartamento.nombre;
          if (departamentoIdInput) departamentoIdInput.value = matchedDepartamento.id;
        } else if (employee.departamento_id && departamentoIdInput) {
          departamentoIdInput.value = employee.departamento_id;
        }

        const cargos = matchedDepartamento ? (matchedDepartamento.cargos || []).filter((item) => (item.estado || 'Activo') === 'Activo') : [];
        if (cargoSelect) {
          if (matchedDepartamento) {
            cargoSelect.innerHTML = [
              '<option value="">Seleccione un cargo</option>',
              ...cargos.map((item) => `<option value="${item.nombre}">${item.nombre}</option>`),
            ].join('');
            cargoSelect.disabled = !cargos.length;
          } else if (employee.cargo || employee.cargo_id) {
            const legacyCargoName = employee.cargo || `Cargo ${employee.cargo_id || ''}`;
            cargoSelect.innerHTML = [
              '<option value="">Seleccione un cargo</option>',
              `<option value="${legacyCargoName}" selected>${legacyCargoName} (inactivo)</option>`,
            ].join('');
            cargoSelect.disabled = true;
          }
        }

        const matchedCargo = cargos.find((item) => item.nombre === employee.cargo || Number(item.id) === Number(employee.cargo_id));
        const cargoIdInput = this.form.querySelector('[name="cargo_id"]');
        if (matchedCargo && cargoSelect) {
          cargoSelect.value = matchedCargo.nombre;
          if (cargoIdInput) cargoIdInput.value = matchedCargo.id;
        } else if (employee.cargo_id && cargoIdInput) {
          cargoIdInput.value = employee.cargo_id;
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
      if (!window.confirm('¿Confirma inhabilitar este empleado?')) {
        return;
      }

      this.setLoading(true);
      try {
        const response = await fetch(`/api/employees/${employeeId}/disable`, { method: 'PATCH' });
        if (!response.ok) throw new Error('Error');
        this.fetchEmployees();
      } catch (error) {
        console.error(error);
        this.showError('No se pudo inhabilitar.');
      } finally {
        this.setLoading(false);
      }
    },
  };

  function debounce(callback, delay = 300) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => callback(...args), delay);
    };
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('employeesList')) {
      EmployeeApp.init();
    }
  });
})();