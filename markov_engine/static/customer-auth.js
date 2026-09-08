/* Clerk owns credentials, verification, recovery and social authorization. */
(async () => {
  const signIn = document.querySelector('[data-clerk-sign-in]');
  const account = document.querySelector('[data-clerk-user]');
  const status = document.querySelector('[data-auth-status]');
  const fail = () => {
    if (status) {
      status.hidden = false;
      status.setAttribute('role', 'alert');
      status.textContent = 'Sign-in could not load. Check your connection and reload this page.';
    }
  };
  try {
    if (!window.Clerk || !window.__internal_ClerkUICtor) throw new Error('Auth unavailable');
    await window.Clerk.load({
      ui: { ClerkUI: window.__internal_ClerkUICtor },
      signInUrl: '/app/login',
      afterSignOutUrl: '/app/login',
      signInFallbackRedirectUrl: '/app/links',
      signUpFallbackRedirectUrl: '/app/links',
      appearance: {
        variables: {
          colorPrimary: '#c44920',
          fontFamily: '"DM Sans", sans-serif',
          borderRadius: '0.625rem',
        },
      },
    });
    if (signIn) {
      if (window.Clerk.isSignedIn) {
        // Refresh before navigating so a stale cookie cannot cause a redirect loop.
        await window.Clerk.session.getToken({ skipCache: true });
        const accepted = await fetch('/app/auth/session', { cache: 'no-store' });
        if (!accepted.ok) throw new Error('Session not accepted');
        window.location.replace('/app/links');
        return;
      }
      window.Clerk.mountSignIn(signIn, {
        routing: 'hash',
        forceRedirectUrl: '/app/links',
        signUpForceRedirectUrl: '/app/links',
        withSignUp: true,
      });
    }
    if (account && window.Clerk.isSignedIn) {
      window.Clerk.mountUserButton(account);
    }
    if (status) status.hidden = true;
  } catch {
    fail();
  }
})();
