<template>
  <div style="position: relative" class="container">
    <div id="primary-img">
      <img :src="displayImgSrc" v-drag />
    </div>
  </div>
</template>
  
  <script>
export default {
  data() {
    return {
      zoom: 1.0,
    };
  },
  props: ["displayImgSrc"],
  methods: {
    closeImage: function () {
      this.zoom = 1;
      this.setImageZoom(this.zoom);
      this.$parent.displayImgSrc = null;
    },
    zoomIn: function () {
      this.zoom += 0.1;
      this.setImageZoom(this.zoom);
    },
    zoomOut: function () {
      if (this.zoom > 1) {
        this.zoom -= 0.1;
        this.setImageZoom(this.zoom);
      }
    },
    setImageZoom(value) {
      const img = document.getElementById("primary-img");
      img.style.transform = `scale(${value})`;
    },
  },
};
</script>

<style scoped lang="scss">
#primary-img {

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    max-height: 75vh;
  }

  @media only screen and (max-width: 900px) {
    img {
      max-height: 60vh;
    }
  }
}
</style>
