<template>
  <v-app class="app">
    <v-main>
      <IndexScreen ref="IndexScreen" />
    </v-main>
  </v-app>
</template>

<script>
import IndexScreen from "./components/IndexScreen";

export default {
  name: "App",
  components: {
    IndexScreen,
  },
  methods: {},
  mounted() {},
};
</script>

<style lang="scss">
.app {
  background-color: #dfccfb !important;
  color: #31302c !important;
  font-family: Jost, sans-serif;
  font-size: 15px;
  margin: 0;
  height: 100%;
  background-size: 40px 40px !important;
  background-image: linear-gradient(90deg, #a2bfae 1px, transparent 0), linear-gradient(180deg, #a2bfae 1px, transparent 0) !important;
  overflow: hidden;
  background-repeat: repeat;
}
</style>
