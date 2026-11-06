import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
  onIdTokenChanged,
  signOut,
  applyActionCode,
  verifyPasswordResetCode,
  confirmPasswordReset,
  fetchSignInMethodsForEmail,
  reauthenticateWithPopup,
} from "firebase/auth";

// Uses Vite env vars if available, with project fallbacks.
// CRITICAL: .trim() prevents trailing newlines/spaces in Cloudflare Pages env vars
// from triggering Error 400: redirect_uri_mismatch during Google OAuth.
const cleanEnv = (val, fallback) => String(val || fallback).trim();

const firebaseConfig = {
  apiKey: cleanEnv(import.meta.env.VITE_FIREBASE_API_KEY, "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"),
  authDomain: cleanEnv(import.meta.env.VITE_FIREBASE_AUTH_DOMAIN, "mediskye-backend.firebaseapp.com"),
  projectId: cleanEnv(import.meta.env.VITE_FIREBASE_PROJECT_ID, "mediskye-backend"),
  storageBucket: cleanEnv(import.meta.env.VITE_FIREBASE_STORAGE_BUCKET, "mediskye-backend.firebasestorage.app"),
  messagingSenderId: cleanEnv(import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID, "1095767703249"),
  appId: cleanEnv(import.meta.env.VITE_FIREBASE_APP_ID, "1:1095767703249:web:c05f08a24d3adc58084ff0")
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

export {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
  onIdTokenChanged,
  signOut,
  applyActionCode,
  verifyPasswordResetCode,
  confirmPasswordReset,
  fetchSignInMethodsForEmail,
  reauthenticateWithPopup,
};

/**
 * Reloads the Firebase user profile and, once emailVerified is true,
 * forces Firebase to mint a fresh JWT (`getIdToken(true)`) with `email_verified: true`.
 */
export const reloadAndGetVerifiedToken = async (user = auth.currentUser) => {
  const targetUser = user || auth?.currentUser;
  if (!targetUser) return { verified: false, token: null };
  if (typeof targetUser.reload === "function") {
    await targetUser.reload();
  }
  const refreshedUser = auth?.currentUser?.emailVerified ? auth.currentUser : targetUser;
  if (refreshedUser && refreshedUser.emailVerified) {
    // CRITICAL: `true` forces Firebase to mint a new JWT with `email_verified: true`
    const token = await refreshedUser.getIdToken(true);
    localStorage.setItem("token", token);
    if (refreshedUser.email) {
      localStorage.setItem("mediskye_user_email", refreshedUser.email);
    }
    return { verified: true, token };
  }
  return { verified: false, token: null };
};

/**
 * Maps Firebase auth error codes to clean, actionable user-facing messages.
 */
export function getFirebaseErrorMessage(error) {
  const code = error?.code;
  switch (code) {
    case 'auth/invalid-credential':
      return "Invalid email or password.";
    case 'auth/wrong-password':
      return "Incorrect password. Please try again.";
    case 'auth/missing-email':
      return "Please enter your email address first.";
    case 'auth/user-not-found':
      return "No account found with this email address.";
    case 'auth/email-already-in-use':
      return "An account with this email already exists. Please log in or reset your password.";
    case 'auth/weak-password':
      return "Password should be at least 6 characters.";
    case 'auth/invalid-email':
      return "Please enter a valid email address.";
    case 'auth/too-many-requests':
      return "Too many failed attempts. Please try again later.";
    case 'auth/user-disabled':
      return "This account has been disabled.";
    case 'auth/popup-closed-by-user':
      return "Google sign-in popup was closed before finishing. Please try again.";
    case 'auth/cancelled-popup-request':
      return "Sign-in popup was interrupted. Please try again.";
    case 'auth/popup-blocked':
      return "Sign-in popup was blocked by your browser. Please allow popups for this site.";
    case 'auth/unauthorized-domain':
      return "This domain is not authorized in Firebase Authentication settings.";
    case 'auth/account-exists-with-different-credential':
      return "An account already exists with this email using a different sign-in method.";
    case 'auth/network-request-failed':
      return "Network error during authentication. Please check your connection and try again.";
    default:
      return "Authentication failed. Please try again.";
  }
}

// Keep localStorage token fresh automatically when Firebase background-rotates ID tokens
if (typeof window !== "undefined" && typeof onIdTokenChanged === "function") {
  try {
    onIdTokenChanged(auth, async (user) => {
      if (user && user.emailVerified !== false) {
        try {
          const token = await user.getIdToken();
          localStorage.setItem("token", token);
          if (user.email) {
            localStorage.setItem("mediskye_user_email", user.email);
          }
        } catch (e) {
          // Token refresh failure (e.g. offline)
        }
      }
    });
  } catch (err) {
    // In unit testing environments where auth might be a mock object
  }
}
