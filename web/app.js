const form = document.querySelector('#question-form');
const role = document.querySelector('#role');
const question = document.querySelector('#question');
const submit = document.querySelector('#submit');
const answer = document.querySelector('#answer');
const status = document.querySelector('#status');
const model = document.querySelector('#model');
const context = document.querySelector('#context');
const panel = document.querySelector('#context-panel');
const improvise = document.querySelector('#improvise');
const newFacts = document.querySelector('#new-facts');
const newFactsPanel = document.querySelector('#new-facts-panel');
let generation = 0;
let controller = null;

function clearResult() {
  answer.textContent = '';
  model.textContent = '';
  context.replaceChildren();
  panel.hidden = true;
  panel.open = false;
  newFacts.replaceChildren();
  newFactsPanel.hidden = true;
  status.textContent = '';
  status.className = '';
}

role.addEventListener('change', () => {
  generation += 1;
  controller?.abort();
  controller = null;
  submit.disabled = false;
  improvise.disabled = false;
  clearResult();
  document.querySelector('#answer-title').textContent = `${role.selectedOptions[0].textContent}的回答`;
  answer.textContent = '身分已切換，請送出問題。';
});

document.querySelectorAll('[data-question]').forEach(button => {
  button.addEventListener('click', () => {
    question.value = button.dataset.question;
    question.focus();
  });
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (submit.disabled) return;
  const text = question.value.trim();
  if (!text) { question.focus(); return; }
  const current = ++generation;
  const selectedRole = role.value;
  const shouldImprovise = improvise.checked;
  controller = new AbortController();
  const activeController = controller;
  clearResult();
  submit.disabled = true;
  improvise.disabled = true;
  status.textContent = shouldImprovise ? '正在檢查世界設定並詢問 AI…' : '正在詢問 AI…';
  const timer = setTimeout(() => activeController.abort(), 105000);
  try {
    const response = await fetch('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: selectedRole, question: text, improvise: shouldImprovise }),
      signal: activeController.signal,
    });
    const data = await response.json();
    if (current !== generation || role.value !== selectedRole) return;
    if (!response.ok) throw new Error(data.error || '詢問失敗，請稍後再試。');
    if (data.role !== selectedRole) throw new Error('回覆身分不符，請重新詢問。');
    answer.textContent = data.answer;
    model.textContent = `實際模型：${data.model}`;
    if (data.editor_model) model.textContent += ` · 設定編輯：${data.editor_model}`;
    (data.new_facts || []).forEach(fact => {
      const item = document.createElement('li');
      item.textContent = `${fact.id}　${fact.text}`;
      newFacts.append(item);
    });
    newFactsPanel.hidden = !data.new_facts?.length;
    data.context.forEach(fact => {
      const item = document.createElement('li');
      item.textContent = `${fact.id}　${fact.text}`;
      context.append(item);
    });
    panel.hidden = false;
    status.textContent = data.new_facts?.length ? `回答完成，已保存 ${data.new_facts.length} 筆新設定。` : '回答完成，本次沒有新增設定。';
  } catch (error) {
    if (current !== generation) return;
    status.className = 'error';
    status.textContent = error.name === 'AbortError'
      ? '等待逾時，請稍後手動重試；原請求仍可能產生費用。'
      : error instanceof TypeError ? '無法連線到本機服務，請確認服務仍在執行。' : error.message;
  } finally {
    clearTimeout(timer);
    if (current === generation) { submit.disabled = false; improvise.disabled = false; controller = null; }
  }
});

fetch('/api/status').then(response => {
  if (!response.ok) throw new Error();
  return response.json();
}).then(data => {
  const missing = [];
  if (!data.key_configured) missing.push('API 金鑰');
  if (!data.model_configured) missing.push('模型名稱');
  document.querySelector('#connection').textContent = missing.length
    ? `尚未設定${missing.join('、')}。請依 README 操作，或使用 start.ps1 啟動。`
    : '本機設定已就緒。送出問題後，才能確認 AI 連線與帳號額度。';
}).catch(() => {
  document.querySelector('#connection').textContent = '無法檢查本機設定，請確認服務仍在執行。';
});
