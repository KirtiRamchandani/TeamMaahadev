<template>
  <div class="modal">
    <div class="modal-header">
      <span class="modal-icon close" @click="kcloseLogsModal()"></span>
      <span class="modal-icon"></span>
      <span class="modal-icon"></span>
    </div>
    <div class="modal-body">
      <DroneImage />
      <div class="logs">
        <ul v-if="logs.length">
          <li v-for="(log, index) in logs" :key="index">
            {{ log }}
          </li>
        </ul>
        <p v-else>No logs found.</p>
      </div>
    </div>
  </div>
</template>

<script src="../scripts/LogsModal.js"></script>
<style scoped src="../styles/Modal.scss" lang="scss"></style>
<style scoped src="../styles/LogsModal.scss" lang="scss"></style>
