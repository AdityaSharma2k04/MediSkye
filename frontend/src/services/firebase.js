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
  sendEmailVerification,
} from "firebase/auth";

// Uses Vite env vars if available, with project fallbacks
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "mediskye-backend.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "mediskye-backend",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "mediskye-backend.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "1095767703249",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:1095767703249:web:c05f08a24d3adc58084ff0"
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
  sendEmailVerification,
};

/**
 * Maps Firebase auth error codes to clean, actionable user-facing messages.
 */
export function getFirebaseErrorMessage(error) {
  const code = error?.code;
  switch (code) {
    case 'auth/invalid-credential':
      return "Invalid email or password. (If you originally signed up with Google, please click 'Continue with Google'.)";
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
      return "Please enter a valid email address (e.g., name@example.com).";
    case 'auth/too-many-requests':
      return "Too many reset attempts. Please wait a few minutes and try again.";
    case 'auth/user-disabled':
      return "This account has been disabled.";
    case 'auth/network-request-failed':
      return "Network error. Please check your internet connection.";
    case 'auth/popup-closed-by-user':
      return "Sign-in popup was closed before completing.";
    default:
      return error?.message || "Authentication failed. Please try again.";
  }
}

// Keep localStorage token fresh automatically when Firebase background-rotates ID tokens
if (typeof window !== "undefined" && typeof onIdTokenChanged === "function") {
  try {
    onIdTokenChanged(auth, async (user) => {
      if (user) {
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
