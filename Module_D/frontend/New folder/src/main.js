import Vue from "vue";
import App from "./App.vue";
import vuetify from "./plugins/vuetify";
import drag from "v-drag";

Vue.config.productionTip = false;
Vue.use(drag);

new Vue({
  vuetify,
  render: (h) => h(App),
}).$mount("#app");
