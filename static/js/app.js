(() => {
  'use strict';

  const seriesList = document.getElementById('series-list');
  const addSeriesButton = document.getElementById('add-series');
  const maxSeries = 8;

  function updateSeriesNumbers() {
    if (!seriesList) return;
    [...seriesList.querySelectorAll('[data-series-row]')].forEach((row, index) => {
      const label = row.querySelector('.series-index');
      if (label) label.textContent = `CASE ${index + 1}`;
      const remove = row.querySelector('.remove-series');
      if (remove) remove.disabled = seriesList.querySelectorAll('[data-series-row]').length <= 1;
    });
  }

  function createSeriesRow(label = '', values = '') {
    const row = document.createElement('div');
    row.className = 'series-row';
    row.setAttribute('data-series-row', '');

    const header = document.createElement('div');
    header.className = 'series-row-head';
    const index = document.createElement('span');
    index.className = 'series-index';
    index.textContent = 'CASE';
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'remove-series';
    remove.setAttribute('aria-label', 'Remove this series');
    remove.title = 'Remove this series';
    remove.textContent = '×';
    header.append(index, remove);

    const labelGroup = document.createElement('div');
    labelGroup.className = 'field-group compact-field';
    const labelText = document.createElement('label');
    labelText.textContent = 'Curve label';
    const labelInput = document.createElement('input');
    labelInput.type = 'text';
    labelInput.name = 'series_label[]';
    labelInput.maxLength = 80;
    labelInput.placeholder = 'e.g. Hall parameter m = 1.0';
    labelInput.value = label;
    labelGroup.append(labelText, labelInput);

    const valuesGroup = document.createElement('div');
    valuesGroup.className = 'field-group compact-field';
    const valuesLabel = document.createElement('label');
    valuesLabel.textContent = 'Y-axis values';
    const valuesInput = document.createElement('textarea');
    valuesInput.name = 'series_values[]';
    valuesInput.rows = 2;
    valuesInput.required = true;
    valuesInput.placeholder = 'Enter values in the same order as X';
    valuesInput.value = values;
    valuesGroup.append(valuesLabel, valuesInput);

    row.append(header, labelGroup, valuesGroup);
    return row;
  }

  if (addSeriesButton && seriesList) {
    addSeriesButton.addEventListener('click', () => {
      const count = seriesList.querySelectorAll('[data-series-row]').length;
      if (count >= maxSeries) {
        window.alert(`You can compare up to ${maxSeries} curves on one graph.`);
        return;
      }
      seriesList.appendChild(createSeriesRow(`Case ${count + 1}`, ''));
      updateSeriesNumbers();
      const last = seriesList.querySelector('[data-series-row]:last-child input[name="series_label[]"]');
      if (last) last.focus();
    });
    seriesList.addEventListener('click', (event) => {
      const button = event.target.closest('.remove-series');
      if (!button) return;
      const row = button.closest('[data-series-row]');
      if (row && seriesList.querySelectorAll('[data-series-row]').length > 1) {
        row.remove();
        updateSeriesNumbers();
      }
    });
    updateSeriesNumbers();
  }

  function setField(id, value) {
    const field = document.getElementById(id);
    if (field) field.value = value;
  }

  document.querySelectorAll('[data-sample-profile]').forEach((button) => {
    button.addEventListener('click', () => {
      setField('x_values', button.dataset.exampleX || '');
      const firstRow = seriesList?.querySelector('[data-series-row]');
      if (firstRow) {
        const label = firstRow.querySelector('input[name="series_label[]"]');
        const values = firstRow.querySelector('textarea[name="series_values[]"]');
        if (label) label.value = button.dataset.exampleLabel || 'Illustrative case';
        if (values) values.value = button.dataset.exampleY || '';
      }
      window.scrollTo({ top: document.getElementById('graph-form')?.offsetTop || 0, behavior: 'smooth' });
    });
  });

  document.querySelectorAll('[data-sample-ann]').forEach((button) => {
    button.addEventListener('click', () => {
      setField('actual_values', '1.2, 1.5, 1.8, 2.0, 2.4, 2.8');
      setField('predicted_values', '1.21, 1.48, 1.82, 1.99, 2.39, 2.77');
    });
  });

  document.querySelectorAll('[data-sample-performance]').forEach((button) => {
    button.addEventListener('click', () => {
      setField('epochs', '1, 2, 3, 4, 5, 6, 7, 8');
      setField('training_mse', '0.08, 0.04, 0.018, 0.009, 0.004, 0.002, 0.0012, 0.0008');
      setField('validation_mse', '0.09, 0.045, 0.021, 0.011, 0.006, 0.004, 0.0045, 0.0052');
      setField('testing_mse', '0.10, 0.05, 0.023, 0.012, 0.007, 0.005, 0.0051, 0.0058');
    });
  });

  // Prevent accidental multiple submissions while the server generates the figures.
  const form = document.getElementById('graph-form');
  if (form) {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.querySelector('span:first-child').textContent = 'Generating…';
      }
    });
  }

  // After successful generation, bring the result section into view.
  const result = document.getElementById('generated-graph');
  if (result) {
    window.setTimeout(() => result.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
  }
})();
