<template>
  <div class="modal">
    <div class="modal-header">
      <span class="modal-icon close" @click="kcloseDroneModal()"></span>
      <span class="modal-icon"></span>
      <span class="modal-icon"></span>
    </div>
    <div class="modal-body">
      <video
        v-for="(video, index) in videos"
        :key="index"
        autoplay
        muted
        playsinline
        loop
        class="drone-video"
        :src="video.src"
      ></video>
    </div>
  </div>
</template>

<style scoped lang="scss">
  .modal-body {
    padding: 0px 30px !important;
  }
  .drone-video {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
</style>

<script>
  import { dronePiConfig } from '../scripts/dronePiConfig';
  export default {
      data() {
        return {
            videos: dronePiConfig
        }
    },
      methods: {
          kclosePiModal: function () {
              this.$parent.$data.isPiFolderOpen = false;
          }
      },
  };
</script>
<style scoped src="../styles/Modal.scss" lang="scss"></style>
