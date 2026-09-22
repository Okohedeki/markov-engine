'use strict';

function initializePairing() {
  const form = document.querySelector('[data-pair-form]');
  if (!form) return;
  const code = new URLSearchParams(location.hash.slice(1)).get('code') || '';
  // Fragments never reach the server logs; remove this one from visible history too.
  history.replaceState(null, '', location.pathname);
  if (!/^[A-Za-z0-9_-]{43}$/.test(code)) return;
  form.querySelector('[data-pair-code]').value = code;
  const submit = form.querySelector('[data-pair-submit]');
  const message = form.querySelector('[data-pair-message]');
  submit.disabled = false;
  message.textContent = 'Invitation ready. Check the service above, then connect.';
  form.addEventListener('submit', () => {
    submit.disabled = true;
    message.textContent = 'Connecting to your service…';
  });
}
initializePairing();

function initializeInvitationExpiry() {
  const label = document.querySelector('[data-invitation-expiry]');
  if (!label) return;
  const update = () => {
    const remaining = Math.max(0, Number(label.dataset.invitationExpiry) - Math.floor(Date.now() / 1000));
    label.textContent = remaining
      ? `Works once. Expires in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}.`
      : 'This invitation has expired. Create a fresh code to connect.';
    label.parentElement.classList.toggle('expired', !remaining);
    if (!remaining) clearInterval(timer);
  };
  const timer = setInterval(update, 1000);
  update();
}
initializeInvitationExpiry();
