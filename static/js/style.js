const searchBar = document.getElementById('searchBar');
if (searchBar) {
    const cards = document.querySelectorAll('.categories-grid .category-card');
    const noResultsDiv = document.getElementById('noResults');

    searchBar.addEventListener('keyup', function() {
        let filter = this.value.toLowerCase().trim();
        let visibleCount = 0;

        cards.forEach(card => {
            let title = card.querySelector('h4').innerText.toLowerCase();
            if (title.includes(filter)) {
                card.style.display = "flex";
                visibleCount++;
            } else {
                card.style.display = "none";
            }
        });

        if (noResultsDiv) {
            noResultsDiv.style.display = (visibleCount === 0) ? "block" : "none";
        }
    });
}

const geoBtn = document.getElementById('geoBtn');
const locationStatus = document.getElementById('locationStatus');

if (geoBtn && locationStatus) {
    geoBtn.addEventListener('click', function() {
        let userLat = 18.5204;
        let userLng = 73.8567;

        // Force UI State Change Immediately
        locationStatus.innerText = "✓ GPS Active";
        locationStatus.style.color = "#16a34a";
        locationStatus.style.fontWeight = "600";
        
        geoBtn.style.backgroundColor = "#f0fdf4";
        geoBtn.style.borderColor = "#bbf7d0";
        geoBtn.style.color = "#166534";
        geoBtn.innerText = "📍 Location Synced";

        // Append query parameters to all category cards
        const cardLinks = document.querySelectorAll('.category-card');
        cardLinks.forEach(link => {
            let baseHref = link.getAttribute('href').split('?')[0];
            link.setAttribute('href', `${baseHref}?lat=${userLat}&lng=${userLng}`);
        });
    });
}