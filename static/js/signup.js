document.getElementById('signupForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageDiv = document.getElementById('message');

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok) {
            messageDiv.innerHTML = '<p class="success">Account created! Redirecting to login...</p>';
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
        } else {
            // Display specific error like "Email already registered"
            messageDiv.innerHTML = `<p class="error">${data.detail || 'Registration failed'}</p>`;
        }
    } catch (error) {
        messageDiv.innerHTML = '<p class="error">Server error. Please try again later.</p>';
    }
});