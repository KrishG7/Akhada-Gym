// Wait for the document to be fully loaded
document.addEventListener("DOMContentLoaded", () => {
  // Find the buttons on the main page
  const bookPassBtn = document.getElementById("one-day-pass-btn");
  const takeTourBtn = document.getElementById("take-tour-btn");

  // State for the modal
  let bookingType = "one_day_pass";
  let generatedOTP = "";
  
  // --- Create the Modal Structure ---
  const modalContainer = document.createElement("div");
  modalContainer.id = "booking-modal-container";
  modalContainer.className = "fixed inset-0 z-50 flex items-center justify-center p-4 hidden";
  document.body.appendChild(modalContainer);

  // Function to show the modal
  function showModal(type) {
    bookingType = type;
    updateModalContent("details");
    modalContainer.classList.remove("hidden");
  }

  // Function to hide the modal
  function hideModal() {
    modalContainer.classList.add("hidden");
  }

  // --- Modal Content for each step ---
  function updateModalContent(step, data = {}) {
    let content = "";
    const title = bookingType === "one_day_pass" ? "One Day Pass" : "Gym Tour";
    const amount = bookingType === "one_day_pass" ? 500 : 200;

    // Base template structure
    content = `
      <div class="absolute inset-0 bg-black/60" id="modal-overlay"></div>
      <div class="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-auto z-10">
        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b border-neutral-200">
          <h2 class="text-lg font-semibold text-neutral-900">Book ${title}</h2>
          <button id="modal-close-btn" class="text-neutral-500 hover:text-neutral-800">&times;</button>
        </div>
        <!-- Step-specific content will go here -->
        <div class="p-6">
    `;

    // --- Step 1: Details Form ---
    if (step === "details") {
      content += `
        <form id="details-form" class="space-y-4">
          <div class="space-y-2">
            <label for="name" class="block text-sm font-medium text-neutral-700">Full Name</label>
            <input type="text" name="name" id="name" class="form-input w-full rounded-md border-neutral-300 shadow-sm text-neutral-900" required>
          </div>
          <div class="space-y-2">
            <label for="phone" class="block text-sm font-medium text-neutral-700">Phone Number (10 digits)</label>
            <input type="tel" name="phone" id="phone" class="form-input w-full rounded-md border-neutral-300 shadow-sm text-neutral-900" 
                required 
                pattern="[0-9]{10}"
                title="Phone number must be exactly 10 digits (no spaces/dashes).">
          </div>
          <div class="space-y-2">
            <label for="email" class="block text-sm font-medium text-neutral-700">Email</label>
            <input type="email" name="email" id="email" class="form-input w-full rounded-md border-neutral-300 shadow-sm text-neutral-900" required>
          </div>
          <div class="p-4 bg-primary-50 border border-primary-200 rounded-lg flex justify-between items-center">
            <span class="font-medium text-primary-800">Total Amount:</span>
            <span class="text-2xl font-bold text-primary-600">₹${amount}</span>
          </div>
          <button type="submit" class="w-full bg-primary-600 hover:bg-primary-700 text-white font-medium py-3 rounded-lg shadow-md">
            Send OTP
          </button>
        </form>
      `;
    }

    // --- Step 2: OTP (Visible on Screen) ---
    if (step === "otp") {
      generatedOTP = String(Math.floor(100000 + Math.random() * 900000));
      
      // FIX: Display OTP prominently on the modal itself
      content += `
        <div class="p-4 bg-red-100 border-2 border-red-500 rounded-lg text-center shadow-lg">
            <p class="text-sm text-red-800 font-bold mb-2">FOR DEMO: YOUR OTP IS</p>
            <p class="text-3xl font-extrabold text-red-700 tracking-widest">${generatedOTP}</p>
        </div>
        <form id="otp-form" class="space-y-4 mt-4">
          <div class="space-y-2">
            <label for="otp" class="block text-sm font-medium text-neutral-700">Enter 6-Digit OTP</label>
            <input type="text" name="otp" id="otp" class="form-input w-full rounded-md border-neutral-300 shadow-sm text-center text-2xl tracking-widest text-neutral-900" maxlength="6" required>
          </div>
          <button type="submit" class="w-full bg-primary-600 hover:bg-primary-700 text-white font-medium py-3 rounded-lg shadow-md">
            Verify OTP
          </button>
          <button type="button" id="back-to-details" class="w-full text-sm text-neutral-600 hover:text-neutral-900">Back</button>
        </form>
      `;
    }
    
    // --- Step 3: Payment (Confirmation) ---
    if (step === "payment") {
      content += `
        <div class="space-y-4">
            <h3 class="text-lg font-medium text-neutral-900">Confirm Booking</h3>
            <p class="text-sm text-neutral-600">Your details are verified. Confirm your booking to generate your pass. You pay at the gym reception; nothing is charged online.</p>
            <div class="p-4 bg-neutral-50 border border-neutral-200 rounded-lg space-y-2 text-neutral-900">
                <div class="flex justify-between"><span class="text-neutral-500">Name:</span> <span class="font-medium">${data.name}</span></div>
                <div class="flex justify-between"><span class="text-neutral-500">Phone:</span> <span class="font-medium">${data.phone}</span></div>
                <div class="flex justify-between"><span class="text-neutral-500">Type:</span> <span class="font-medium">${title}</span></div>
                <div class="flex justify-between pt-2 border-t"><span class="text-neutral-500">Total:</span> <span class="font-bold text-lg text-primary-600">₹${amount}</span></div>
            </div>
            <button id="confirm-booking-btn" class="w-full bg-primary-600 hover:bg-primary-700 text-white font-medium py-3 rounded-lg shadow-md">
                Confirm Booking
            </button>
            <div id="payment-loader" class="hidden text-center">
                <p class="text-neutral-600">Reserving your pass...</p>
            </div>
        </div>
      `;
    }

    // --- Step 4: Ticket ---
    if (step === "ticket") {
      content += `
        <div class="space-y-4 text-center text-neutral-900">
            <h3 class="text-xl font-medium text-neutral-900">Booking Confirmed!</h3>
            <p class="text-sm text-neutral-600">Show this QR code at the reception and pay there.</p>
            
            <!-- This is where the QR code will be rendered -->
            <div id="qr-code-canvas" class="p-4 border-2 border-primary-500 rounded-lg inline-block"></div>
            
            <div class="p-4 bg-neutral-50 border border-neutral-200 rounded-lg space-y-2 text-left">
                <div class="flex justify-between"><span class="text-neutral-500">Booking ID:</span> <span class="font-medium">${data.bookingId}</span></div>
                <div class="flex justify-between"><span class="text-neutral-500">Name:</span> <span class="font-medium">${data.name}</span></div>
                <div class="flex justify-between"><span class="text-neutral-500">Date:</span> <span class="font-medium">${data.date}</span></div>
                <div class="flex justify-between pt-2 border-t"><span class="text-neutral-500">Amount:</span> <span class="font-bold text-lg text-primary-600">₹${data.amount}</span></div>
            </div>
            <button id="modal-done-btn" class="w-full bg-neutral-700 hover:bg-neutral-800 text-white font-medium py-3 rounded-lg shadow-md">
                Done
            </button>
        </div>
      `;
    }

    // Close the base template
    content += `
        </div> <!-- End p-6 -->
      </div> <!-- End bg-white -->
    `;

    modalContainer.innerHTML = content;

    // --- Add Event Listeners for the new content ---
    
    // Always add listeners for close buttons
    document.getElementById("modal-overlay")?.addEventListener("click", hideModal);
    document.getElementById("modal-close-btn")?.addEventListener("click", hideModal);
    
    // --- Step 1 Listeners ---
    const detailsForm = document.getElementById("details-form");
    if (detailsForm) {
      detailsForm.addEventListener("submit", (e) => {
        e.preventDefault();
        
        // Manual Validation Check
        const phoneInput = document.getElementById("phone");
        if (phoneInput && phoneInput.validity.patternMismatch) {
          alert("Please enter a valid 10-digit phone number.");
          return;
        }

        const formData = new FormData(detailsForm);
        const data = Object.fromEntries(formData.entries());
        // Store data and move to OTP step
        updateModalContent("otp", data);
      });
    }

    // --- Step 2 Listeners ---
    const otpForm = document.getElementById("otp-form");
    if (otpForm) {
      document.getElementById("back-to-details")?.addEventListener("click", () => updateModalContent("details"));
      otpForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const enteredOTP = document.getElementById("otp").value;
        if (enteredOTP === generatedOTP) {
          // Get the data we stored from the previous step
          const name = document.getElementById("name")?.value || data.name;
          const phone = document.getElementById("phone")?.value || data.phone;
          const email = document.getElementById("email")?.value || data.email;
          updateModalContent("payment", { name, phone, email });
        } else {
          alert("Incorrect OTP. Please try again.");
        }
      });
    }

    // --- Step 3 Listeners ---
    const confirmBtn = document.getElementById("confirm-booking-btn");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", async () => {
        // Show loader, hide button
        confirmBtn.classList.add("hidden");
        document.getElementById("payment-loader").classList.remove("hidden");

        // --- THIS IS THE API CALL ---
        try {
          const response = await fetch("/api/book_pass", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: data.name,
              phone: data.phone,
              email: data.email,
              bookingType: bookingType,
            }),
          });
          
          const result = await response.json();

          if (result.success) {
            // Move to ticket step
            updateModalContent("ticket", { ...data, ...result });
          } else {
            throw new Error(result.error);
          }
        } catch (err) {
          alert("Booking failed: " + err.message);
          updateModalContent("payment", data); 
        }
      });
    }
    
    // --- Step 4 Listeners ---
    const qrCanvas = document.getElementById("qr-code-canvas");
    if (qrCanvas) {
      // Generate the QR Code using the library
      QRCode.toString(data.qrData, { type: 'svg' }, (err, svgString) => {
        if (err) throw err;
        qrCanvas.innerHTML = svgString;
        qrCanvas.firstChild.style.width = "200px";
        qrCanvas.firstChild.style.height = "200px";
      });
    }
    document.getElementById("modal-done-btn")?.addEventListener("click", hideModal);
    
  } // --- End of updateModalContent function ---

  // --- Initial Page Event Listeners ---
  if (bookPassBtn) {
    bookPassBtn.addEventListener("click", () => showModal("one_day_pass"));
  }
  if (takeTourBtn) {
    takeTourBtn.addEventListener("click", () => showModal("gym_tour"));
  }
});