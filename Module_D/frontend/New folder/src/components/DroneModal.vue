<template>
  <div class="modal">
    <div class="modal-header">
      <span class="modal-icon close" @click="kcloseDroneModal()"></span>
      <span class="modal-icon"></span>
      <span class="modal-icon"></span>
    </div>
    <div class="modal-body">
      <DroneImage />
      <MapComponent ref="mapComponent" />
    </div>
  </div>
</template>

<script src="../scripts/DroneModal.js"></script>
<style scoped src="../styles/Modal.scss" lang="scss"></style>
<style scoped src="../styles/DroneModal.scss" lang="scss"></style>
