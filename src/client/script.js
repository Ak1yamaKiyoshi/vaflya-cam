document.addEventListener("DOMContentLoaded", function() {
    const themeSwitch = document.getElementById("theme-switch");
    const screenImage = document.getElementById('screen');
    const video = document.getElementById('video');
    
    // Debug - check if screen element exists
    console.log("Screen element:", screenImage);
    
    const serverAddress = 'vaflya.local';
    const serverPort = 5000;  // Using your image server port
    
    // Theme switcher logic
    themeSwitch.addEventListener("change", function() {
        if(this.checked) {
            document.body.classList.remove("dark-theme");
            document.body.classList.add("light-theme");
            localStorage.setItem("theme", "light");
        } else {
            document.body.classList.remove("light-theme");
            document.body.classList.add("dark-theme");
            localStorage.setItem("theme", "dark");
        }
    });

    const savedTheme = localStorage.getItem("theme");
    if(savedTheme === "light") {
        themeSwitch.checked = true;
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
    }
    
    // Control event listeners
    const redGain = document.getElementById("redGain");
    redGain.addEventListener("change", async () => {
        const redGainValue = redGain.value;
        document.getElementById("redGainVal").textContent = redGainValue;
        const payload = {
            value: redGainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/red_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const blueGain = document.getElementById("blueGain");
    blueGain.addEventListener("change", async () => {
        const blueGainValue = blueGain.value;
        document.getElementById("blueGainVal").textContent = blueGainValue;
        const payload = {
            value: blueGainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/blue_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const analogueGain = document.getElementById("gain");
    analogueGain.addEventListener("change", async () => {
        const gainValue = analogueGain.value;
        document.getElementById("gainVal").textContent = gainValue;
        const payload = {
            value: gainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/analogue_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const exposure = document.getElementById("shutterSpeed1");
    exposure.addEventListener("change", async () => {
        const exposureValue = exposure.value;
        const payload = {
            value: Math.log(exposureValue*0.3 + 1) * 1_000_000
        };
        document.getElementById("shutterSpeed1Val").textContent = payload.value.toFixed(0);
        try {
            const response = await fetch(`http://${serverAddress}:4500/exposure_time`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const captureButton = document.getElementById("capture");
    if (captureButton) {
        captureButton.addEventListener("click", async function() {
            try {
                const response = await fetch(`http://${serverAddress}:4500/capture`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });
            } catch (error) {
                console.error("Request failed:", error);
            }
        });
    }
    
    // Image streaming setup
    let frameCount = 0;
    let dataSize = 0;
    let latency = 0;

    // Show the image element, hide video
    video.style.display = 'none';
    screenImage.style.display = 'block';

    // Utility function to decompress data if needed
    function decompressData(compressedData) {
        try {
            const binaryString = atob(compressedData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            return bytes;
        } catch (e) {
            console.error('Error decompressing:', e);
            return null;
        }
    }

    let fetchInProgress = false;
    const maxFPS = 25;
    const minFrameTime = 1000 / maxFPS;
    let lastFrameTime = 0;
    let lastFetchTime = Date.now();

    function scheduleFetch() {
        const now = Date.now();
        const elapsed = now - lastFrameTime;
        const delay = Math.max(0, minFrameTime - elapsed);
        setTimeout(fetchImage, delay);
    }

    function checkFetchTimeout() {
        const now = Date.now();
        const timeSinceLastFetch = now - lastFetchTime;
        
        // If no fetch in the last 2 seconds and no fetch is currently in progress, trigger a new fetch
        if (timeSinceLastFetch > 2000 && !fetchInProgress) {
            console.log("Connection timeout, attempting to reconnect...");
            fetchImage();
        }
        
        setTimeout(checkFetchTimeout, 1000);
    }

    checkFetchTimeout();

    function fetchImage() {
        if (fetchInProgress) {
            return;
        }
        
        fetchInProgress = true;
        lastFrameTime = Date.now();
        const startTime = Date.now();
        
        fetch(`http://${serverAddress}:${serverPort}/c?${startTime}`)
            .then(r => {
                return r.text();
            })
            .then(encodedData => {
                console.log("Received data, first 40 chars:", encodedData.substring(0, 40));
                
                if (encodedData.startsWith('data:image')) {
                    screenImage.src = encodedData;
                } else {
                    // Fallback if the data isn't already in the expected format
                    screenImage.src = encodedData;
                }

                dataSize += encodedData.length;
                frameCount++;
                latency = Date.now() - startTime;
                
                fetchInProgress = false;
                lastFetchTime = Date.now(); // Update the last fetch time
                scheduleFetch();
            })
            .catch(err => {
                console.error('Fetch error:', err);
                fetchInProgress = false;
                lastFetchTime = Date.now(); // Update even on error to prevent immediate retries on persistent errors
                setTimeout(fetchImage, 500);
            });
    }

    // Start fetching images
    fetchImage();
});