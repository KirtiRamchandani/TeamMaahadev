const MapComponent = () => import("../components/MapsComponent.vue");
const DroneImage = () => import("../components/DroneImage.vue");

export default {
    components: {
        MapComponent,
        DroneImage
    },
    methods: {
        kcloseDroneModal: function () {
            this.$parent.$data.isDroneFolderOpen = false;
        }
    },
};