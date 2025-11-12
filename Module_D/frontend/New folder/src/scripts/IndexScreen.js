const DroneModal = () => import("../components/DroneModal");
const LogsModal = () => import("../components/LogsModal");
const FolderClose = () => import("../components/FolderClose");
const FolderOpen = () => import("../components/FolderOpen");
const DroneSettingsModal = () => import("../components/DroneSettingsModal");
const DroneCapturesModal = () => import("../components/DroneCapturesModal");
const DronePiModal = () => import("../components/DronePIModal");

export default {
  name: "IndexScreen",
  components: {
    DroneModal,
    LogsModal,
    FolderClose,
    FolderOpen,
    DroneSettingsModal,
    DroneCapturesModal,
    DronePiModal
  },
  data() {
    return {
      isDroneFolderOpen: true,
      isLogsFolderOpen: false,
      isSettingsFolderOpen: false,
      isCapturesFolderOpen: false,
      isPiFolderOpen: false,
    };
  },
  methods: {
    openKCloseHome: function () {
      this.kcloseOtherModals("Drone");
      this.isDroneFolderOpen = !this.isDroneFolderOpen;
    },
    openKCloseProjects: function () {
      this.kcloseOtherModals("Logs");
      this.isLogsFolderOpen = !this.isLogsFolderOpen;
    },
    openKCloseSettings: function () {
      this.kcloseOtherModals("Settings");
      this.isSettingsFolderOpen = !this.isSettingsFolderOpen;
    },
    openKCloseCaptures: function () {
      this.kcloseOtherModals("Captures");
      this.isCapturesFolderOpen = !this.isCapturesFolderOpen;
    },
    openKClosePi: function () {
      this.kcloseOtherModals("Pi");
      this.isPiFolderOpen = !this.isPiFolderOpen;
    },
    kcloseOtherModals: function (clickedModal) {
      if (clickedModal !== "Drone") this.isDroneFolderOpen = false;
      if (clickedModal !== "Logs") this.isLogsFolderOpen = false;
      if (clickedModal !== "Settings") this.isSettingsFolderOpen = false;
      if (clickedModal !== "Captures") this.isCapturesFolderOpen = false;
      if (clickedModal !== "Pi") this.isPiFolderOpen = false;
    },
  },
};
