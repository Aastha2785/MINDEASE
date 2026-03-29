document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const messageDiv = document.getElementById('message');

    // FastAPI's OAuth2 expects form-data for login
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    try {
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // Save the token to use for other requests
            localStorage.setItem('access_token', data.access_token);
            messageDiv.innerHTML = '<p class="success">Login Successful! Redirecting...</p>';
            
            // Redirect to dashboard after 1 second
            setTimeout(() => { window.location.href = '/dashboard'; }, 1000);
        } else {
            messageDiv.innerHTML = `<p class="error">${data.detail}</p>`;
        }
    } catch (error) {
        messageDiv.innerHTML = '<p class="error">Something went wrong. Try again.</p>';
    }
});