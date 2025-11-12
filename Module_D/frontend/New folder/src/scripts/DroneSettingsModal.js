const DroneImage = () => import("../components/DroneImage.vue");

export default {
    components: {
        DroneImage
    },
    data() {
        return {
            droneOn: false,
            headers: [
                { text: "Detail", value: "key", align: "start" },
                { text: "Information", value: "value", align: "start" },
            ],
            droneDetails: [
                { key: "Drone Name", value: "Clover 4" },
                { key: "Operating System", value: "Linux Distro" },
                { key: "Circuit Information", value: "Raspberry Pi 4" },
                { key: "Local Address", value: "192.168.1.1" },
                { key: "Connection Type", value: "SSH" },
                { key: "Port Number", value: "22" },
                { key: "Origin Path", value: "https://kirtikumarar.com" },
            ],
        };
    },
    methods: {
        kcloseDroneModal: function () {
            this.$parent.$data.isSettingsFolderOpen = false;
        },
        isLink: function (value) {
            return value.startsWith("http");
        },
        turnOnDrone() {
            this.droneOn = true;
        },
        turnOffDrone() {
            this.droneOn = false;
        },
    },
};