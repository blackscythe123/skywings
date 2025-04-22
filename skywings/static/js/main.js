// Common JS functions for the flight booking system

document.addEventListener('DOMContentLoaded', function() {
    // Initialize date pickers with min date of today
    const today = new Date().toISOString().split('T')[0];
    const departureDateInput = document.getElementById('departure-date');
    const returnDateInput = document.getElementById('return-date');
    
    if (departureDateInput) {
        departureDateInput.setAttribute('min', today);
        departureDateInput.addEventListener('change', function() {
            if (returnDateInput) {
                returnDateInput.setAttribute('min', this.value);
                // If return date is before departure date, reset it
                if (returnDateInput.value && returnDateInput.value < this.value) {
                    returnDateInput.value = this.value;
                }
            }
        });
    }
    
    if (returnDateInput) {
        returnDateInput.setAttribute('min', today);
    }
    
    // Trip type radio buttons to show/hide return date
    const tripTypeRadios = document.querySelectorAll('input[name="trip-type"]');
    if (tripTypeRadios.length) {
        tripTypeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                const returnDateGroup = document.querySelector('.return-date-group');
                if (returnDateGroup) {
                    if (this.value === 'round-trip') {
                        returnDateGroup.style.display = 'block';
                    } else {
                        returnDateGroup.style.display = 'none';
                        if (returnDateInput) {
                            returnDateInput.value = '';
                        }
                    }
                }
            });
        });
        
        // Initialize on page load
        const checkedTripType = document.querySelector('input[name="trip-type"]:checked');
        if (checkedTripType && checkedTripType.value === 'one-way') {
            const returnDateGroup = document.querySelector('.return-date-group');
            if (returnDateGroup) {
                returnDateGroup.style.display = 'none';
            }
        }
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Add loading overlay for forms
    const forms = document.querySelectorAll('form:not(.no-loading)');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            showLoadingOverlay();
        });
    });
    
    // Flight selection
    const flightSelectionBtns = document.querySelectorAll('.select-flight-btn');
    flightSelectionBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            showLoadingOverlay();
        });
    });

    // --- Chatbot Functionality ---
    const chatbox = document.getElementById("chatbox");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");

    // Check if we're on the chatbot page (i.e., the required elements exist)
    if (chatbox && userInput && sendBtn) {
        // Add event listener for the "Send" button
        sendBtn.addEventListener("click", sendMessage);

        // Add event listener for the "Enter" key
        userInput.addEventListener("keypress", function (event) {
            if (event.key === "Enter") {
                sendMessage();
            }
        });
    }

    // Function to send a message to the chatbot and display the response
    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === "") return; // Ignore empty messages

        // Display the user's message in the chat
        appendMessage("You", message);
        userInput.value = ""; // Clear the input field

        // Show loading overlay while processing
        showLoadingOverlay();

        try {
            // Send the message to the /chatbot endpoint
            const response = await fetch("/chatbot", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ message: message })
            });

            // Check if the response is OK
            if (!response.ok) {
                throw new Error("Network response was not ok");
            }

            // Parse the JSON response
            const data = await response.json();
            appendMessage("Chatbot", data.response);
        } catch (error) {
            console.error("Error:", error);
            appendMessage("Chatbot", "Sorry, something went wrong. Please try again.");
        } finally {
            // Remove the loading overlay
            const overlay = document.querySelector('.loading-overlay');
            if (overlay) {
                overlay.remove();
            }
        }
    }

    // Function to append a message to the chat UI
    function appendMessage(sender, text) {
        const messageElement = document.createElement("p");
        messageElement.innerHTML = `<strong>${sender}:</strong> ${text}`;
        chatbox.appendChild(messageElement);
        chatbox.scrollTop = chatbox.scrollHeight; // Scroll to the bottom
    }
});

// Show loading overlay
function showLoadingOverlay() {
    const overlay = document.createElement('div');
    overlay.classList.add('loading-overlay');
    
    const spinner = document.createElement('div');
    spinner.classList.add('spinner-border', 'text-light');
    spinner.setAttribute('role', 'status');
    
    const loadingText = document.createElement('span');
    loadingText.classList.add('loading-text');
    loadingText.textContent = 'Processing...';
    
    overlay.appendChild(spinner);
    overlay.appendChild(loadingText);
    document.body.appendChild(overlay);
}

// Format price with 2 decimal places and currency symbol
function formatPrice(price, currency = '$') {
    return currency + parseFloat(price).toFixed(2);
}

// Format date to readable format
function formatDate(dateString) {
    const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', options);
}

// Format time to 12-hour format
function formatTime(dateTimeString) {
    const date = new Date(dateTimeString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// Toggle password visibility
function togglePasswordVisibility(inputId, iconId) {
    const passwordInput = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
}

// Capitalize first letter of each word
function capitalizeWords(str) {
    return str.replace(/\b\w/g, char => char.toUpperCase());
}