/* CayenaBot — auth.js
 * 4-user login (ISA / JAG / PAM / ALV) with per-user localStorage namespace.
 * Avatars + 6-digit password. No server. Internal team use only.
 */

export const USERS = [
  { id: 'ISA', name: 'Isabel',  pass: '151202', color: '#e05090', initials: 'IS', emoji: '🩷' },
  { id: 'JAG', name: 'Jaguar',  pass: '121174', color: '#c4773b', initials: 'JG', emoji: '🧱' },
  { id: 'PAM', name: 'Pamela',  pass: '260572', color: '#5b8def', initials: 'PM', emoji: '💙' },
  { id: 'ALV', name: 'Alvaro',  pass: '221297', color: '#10b981', initials: 'AL', emoji: '💚' },
];

const SESSION_KEY = 'cayenabot_session';

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const obj = JSON.parse(raw);
    return USERS.find(u => u.id === obj.userId) ? obj : null;
  } catch { return null; }
}

export function startSession(userId) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({ userId, since: Date.now() }));
}

export function endSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function findUser(id) { return USERS.find(u => u.id === id); }

export function authenticate(userId, pass) {
  const u = findUser(userId);
  if (!u) return false;
  return u.pass === String(pass).trim();
}

/** Render the avatar grid + password form on the login screen. */
export function mountLoginScreen(onSuccess) {
  const grid = document.getElementById('avatar-grid');
  const form = document.getElementById('password-form');
  const selectedDiv = form.querySelector('.selected-avatar');
  const passInput = document.getElementById('password-input');
  const errEl = document.getElementById('login-error');
  const backBtn = document.getElementById('back-to-avatars');
  let pickedId = null;

  grid.innerHTML = '';
  USERS.forEach(u => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'avatar';
    btn.style.background = u.color;
    btn.title = u.name;
    btn.innerHTML = `${u.initials}<span class="emoji">${u.emoji}</span>`;
    btn.addEventListener('click', () => {
      pickedId = u.id;
      selectedDiv.style.background = u.color;
      selectedDiv.textContent = u.initials;
      grid.hidden = true;
      form.hidden = false;
      errEl.hidden = true;
      passInput.value = '';
      passInput.focus();
    });
    grid.appendChild(btn);
  });

  backBtn.onclick = () => {
    pickedId = null;
    grid.hidden = false;
    form.hidden = true;
  };

  form.onsubmit = (e) => {
    e.preventDefault();
    if (!pickedId) return;
    if (authenticate(pickedId, passInput.value)) {
      startSession(pickedId);
      onSuccess(findUser(pickedId));
    } else {
      errEl.textContent = 'Código incorrecto.';
      errEl.hidden = false;
      passInput.value = '';
      passInput.focus();
    }
  };
}
