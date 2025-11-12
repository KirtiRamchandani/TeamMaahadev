<template>
  <div>
    <div id="map"></div>
  </div>
</template>

<script>
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

export default {
  name: "MapComponent",
  data() {
    return {
      map: null,
      marker: null,
    };
  },
  mounted() {
    this.initMap();
  },
  methods: {
    initMap() {
      this.map = L.map("map").setView([0, 0], 2); // temporary default view
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(
        this.map
      );
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            this.map.setView([lat, lng], 18);
            this.setMarker(lat, lng);
          },
          (error) => {
            console.error("Error getting location:", error);
            alert("Unable to retrieve your location.");
          }
        );
      } else {
        alert("Geolocation is not supported by your browser.");
      }
    },
    setMarker(latitude, longitude) {
      const defaultIcon = L.icon({
        iconUrl: markerIcon,
        iconRetinaUrl: markerIcon2x,
        shadowUrl: markerShadow,
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
      });
      this.map.setView([latitude, longitude], 18);
      if (this.marker) {
        this.map.removeLayer(this.marker);
      }
      this.marker = L.marker([latitude, longitude], {
        icon: defaultIcon,
      }).addTo(this.map);
    },
  },
};
</script>

<style scoped>
#map {
  width: 100%;
  height: 500px;
}

@media only screen and (max-width: 900px) {
  #map {
    height: 300px;
  }
}
</style>
