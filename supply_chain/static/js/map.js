document.addEventListener('DOMContentLoaded', function() {
    // Initialize maps if they exist on the page
    initMaps();
});

function initMaps() {
    const mapContainers = document.querySelectorAll('.map-container');
    
    mapContainers.forEach(container => {
        const mapData = JSON.parse(container.dataset.map);
        
        if (mapData && mapData.coordinates) {
            renderMap(container.id, mapData);
        }
    });
}

function renderMap(mapId, mapData) {
    // Initialize the map
    const map = L.map(mapId).setView(
        [mapData.coordinates[0].lat, mapData.coordinates[0].lng], 
        mapData.zoom || 12
    );
    
    // Add tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add markers for each location
    mapData.coordinates.forEach((coord, index) => {
        const marker = L.marker([coord.lat, coord.lng]).addTo(map);
        
        if (coord.popup) {
            marker.bindPopup(`
                <div class="map-popup">
                    <h6>${coord.popup.title || 'Location'}</h6>
                    <p>${coord.popup.content || ''}</p>
                    ${coord.popup.footer ? `<small>${coord.popup.footer}</small>` : ''}
                </div>
            `);
        }
    });
    
    // Add route if provided
    if (mapData.route && mapData.route.length > 1) {
        const route = L.polyline(
            mapData.route.map(coord => [coord.lat, coord.lng]),
            {color: '#3388ff', weight: 5}
        ).addTo(map);
        
        // Adjust map view to fit the route
        map.fitBounds(route.getBounds());
    }
}

// Utility function for geocoding addresses
async function geocodeAddress(address) {
    try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`);
        const data = await response.json();
        
        if (data && data.length > 0) {
            return {
                lat: parseFloat(data[0].lat),
                lng: parseFloat(data[0].lon)
            };
        }
        return null;
    } catch (error) {
        console.error('Geocoding error:', error);
        return null;
    }
}