import { fetchLogs } from "../utils/db";
const DroneImage = () => import("../components/DroneImage.vue");

export default {
  name: "LogsModal",
  components: {
    DroneImage
},
  data() {
    return {
      logs: []
    };
  },
  async mounted() {
    const logs = await fetchLogs();
    this.logs = [...logs];
  },
  methods: {
    kcloseLogsModal: function () {
      this.$parent.$data.isLogsFolderOpen = false;
    }
  },
};
