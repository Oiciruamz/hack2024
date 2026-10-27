// ==========================================================================
// Autenticación con Firebase (login, registro, Google, recuperar contraseña).
// El navegador obtiene un ID token y lo intercambia en /sesion por una
// sesión de Flask. La persistencia del SDK es en memoria: la sesión del
// servidor es la única fuente de verdad (logout = /logout).
// ==========================================================================
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import {
    getAuth,
    setPersistence,
    inMemoryPersistence,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    updateProfile,
    GoogleAuthProvider,
    signInWithPopup,
    sendPasswordResetEmail,
} from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

const config = window.FIREBASE_CONFIG || {};
const siguiente = window.AUTH_NEXT || '/';

const form = document.getElementById('auth-form');
const errorBox = document.getElementById('error-message');
const infoBox = document.getElementById('info-message');
const submitBtn = document.getElementById('submit-btn');
const googleBtn = document.getElementById('google-btn');
const resetLink = document.getElementById('reset-link');

const MENSAJES = {
    'auth/invalid-credential': 'Error login',
    'auth/wrong-password': 'Error login',
    'auth/user-not-found': 'Error login',
    'auth/invalid-email': 'El correo electrónico no es válido.',
    'auth/email-already-in-use': 'Ya existe una cuenta con ese correo.',
    'auth/weak-password': 'La contraseña debe tener al menos 6 caracteres.',
    'auth/too-many-requests': 'Demasiados intentos. Intenta de nuevo en unos minutos.',
    'auth/popup-closed-by-user': 'Se cerró la ventana de Google antes de terminar.',
    'auth/cancelled-popup-request': 'Se cerró la ventana de Google antes de terminar.',
    'auth/popup-blocked': 'El navegador bloqueó la ventana emergente de Google.',
    'auth/network-request-failed': 'Error de red. Revisa tu conexión.',
    'auth/operation-not-allowed': 'Este método de inicio de sesión no está habilitado.',
};

function mostrar(box, mensaje) {
    if (!box) return;
    box.textContent = mensaje;
    box.hidden = !mensaje;
}

function mostrarError(mensaje) {
    mostrar(infoBox, '');
    mostrar(errorBox, mensaje);
    if (mensaje && errorBox) errorBox.focus();
}

function ocupado(estado) {
    [submitBtn, googleBtn].forEach(b => { if (b) b.disabled = estado; });
    if (submitBtn) {
        submitBtn.dataset.texto ??= submitBtn.textContent;
        submitBtn.textContent = estado ? 'Procesando…' : submitBtn.dataset.texto;
    }
}

function traducirError(err) {
    console.error(err);
    return MENSAJES[err?.code] || 'Ocurrió un error. Intenta de nuevo.';
}

async function crearSesion(user, nombre = '') {
    const idToken = await user.getIdToken();
    const resp = await fetch('/sesion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ idToken, nombre, next: siguiente }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.success) {
        throw { code: 'server', message: data.message || 'No se pudo iniciar sesión.' };
    }
    window.location.assign(data.redirect || '/');
}

function manejarFallo(err) {
    mostrarError(err?.code === 'server' ? err.message : traducirError(err));
    ocupado(false);
}

if (!config.apiKey) {
    mostrarError('El inicio de sesión no está configurado (faltan las variables FIREBASE_* en .env).');
    [submitBtn, googleBtn].forEach(b => { if (b) b.disabled = true; });
} else {
    const app = initializeApp(config);
    const auth = getAuth(app);
    auth.languageCode = 'es';
    await setPersistence(auth, inMemoryPersistence);

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        mostrarError('');
        const modo = form.dataset.modo; // 'login' | 'registro'
        const email = form.email.value.trim();
        const password = form.password.value;
        const nombre = form.nombre ? form.nombre.value.trim() : '';

        if (modo === 'registro' && !nombre) {
            mostrarError('Escribe tu nombre de usuario.');
            return;
        }

        ocupado(true);
        try {
            let cred;
            if (modo === 'registro') {
                cred = await createUserWithEmailAndPassword(auth, email, password);
                await updateProfile(cred.user, { displayName: nombre });
            } else {
                cred = await signInWithEmailAndPassword(auth, email, password);
            }
            await crearSesion(cred.user, nombre);
        } catch (err) {
            manejarFallo(err);
        }
    });

    googleBtn?.addEventListener('click', async () => {
        mostrarError('');
        ocupado(true);
        try {
            const provider = new GoogleAuthProvider();
            provider.setCustomParameters({ prompt: 'select_account' });
            const cred = await signInWithPopup(auth, provider);
            await crearSesion(cred.user, cred.user.displayName || '');
        } catch (err) {
            manejarFallo(err);
        }
    });

    resetLink?.addEventListener('click', async (e) => {
        e.preventDefault();
        const email = form?.email.value.trim();
        if (!email) {
            mostrarError('Escribe tu correo arriba y vuelve a presionar "¿Olvidaste tu contraseña?".');
            form?.email.focus();
            return;
        }
        try {
            await sendPasswordResetEmail(auth, email);
        } catch (err) {
            // No revelar si el correo existe; solo informar errores de formato/red
            if (err?.code !== 'auth/user-not-found') {
                mostrarError(traducirError(err));
                return;
            }
        }
        mostrar(errorBox, '');
        mostrar(infoBox, 'Si existe una cuenta con ese correo, te enviamos un enlace para restablecer tu contraseña.');
    });
}
