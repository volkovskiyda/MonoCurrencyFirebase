const firebaseConfig = {
    apiKey: "AIzaSyBoXhDZ5PS2yJ-XmojhibJZKH12EDWP9dQ",
    authDomain: "monocurrency.firebaseapp.com",
    projectId: "monocurrency",
    storageBucket: "monocurrency.firebasestorage.app",
    messagingSenderId: "593932512297",
    appId: "1:593932512297:web:81e80d7643d472db1d0038",
    measurementId: "G-2WNFFE86XQ"
  };

const app = firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

const googleSignInButton = document.getElementById('google-sign-in-button');
const signOutButton = document.getElementById('sign-out-button');
const userInfoDiv = document.getElementById('user-info');
const userDisplayName = document.getElementById('user-display-name');
const userEmail = document.getElementById('user-email');
const userUID = document.getElementById('user-uid');
const errorMessage = document.getElementById('error-message');

const provider = new firebase.auth.GoogleAuthProvider();

googleSignInButton.addEventListener('click', async () => {
    errorMessage.style.display = 'none';
    try {
        const result = await auth.signInWithPopup(provider);
        const user = result.user;
        console.log('User signed in:', user);
        updateUIForUser(user);
    } catch (error) {
        console.error('Error during Google Sign-in:', error);
        errorMessage.textContent = `Sign-in failed: ${error.message}`;
        errorMessage.style.display = 'block';
    }
});

signOutButton.addEventListener('click', async () => {
    try {
        await auth.signOut();
        console.log('User signed out.');
        updateUIForNoUser();
    } catch (error) {
        console.error('Error during sign-out:', error);
        errorMessage.textContent = `Sign-out failed: ${error.message}`;
        errorMessage.style.display = 'block';
    }
});

function updateUIForUser(user) {
    if (user) {
        googleSignInButton.style.display = 'none';
        userInfoDiv.style.display = 'block';
        userDisplayName.textContent = user.displayName || 'N/A';
        userEmail.textContent = user.email || 'N/A';
        userUID.textContent = user.uid || 'N/A';
    }
}

function updateUIForNoUser() {
    googleSignInButton.style.display = 'flex';
    userInfoDiv.style.display = 'none';
    userDisplayName.textContent = '';
    userEmail.textContent = '';
    userUID.textContent = '';
    errorMessage.style.display = 'none';
}

auth.onAuthStateChanged(async (user) => {
    if (user) {
        const idToken = await user.getIdToken();
        console.log('ID Token:', idToken);
        updateUIForUser(user);
    } else {
        updateUIForNoUser();
    }
});
