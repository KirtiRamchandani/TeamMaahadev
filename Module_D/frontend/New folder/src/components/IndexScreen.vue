<template>
  <div>
    <div class="home-screen">
      <div class="nav-tray">
        <div class="nav-option" @click="openKCloseHome()">
          <folder-open
            v-if="isDroneFolderOpen"
            :style="`--element-color: #c7c7bb`"
          ></folder-open>
          <folder-close
            v-else
            :style="`--element-color: #c7c7bb`"
          ></folder-close>
          <p class="nav-title"> Clover 4 <br /> GPS</p>
        </div>
        <div class="nav-option" @click="openKCloseProjects()">
          <folder-open
            v-if="isLogsFolderOpen"
            :style="`--element-color: #c9c2ea`"
          ></folder-open>
          <folder-close
            v-else
            :style="`--element-color: #c9c2ea`"
          ></folder-close>
          <p class="nav-title"> Clover 4 <br /> Logs</p>
        </div>
        <div class="nav-option" @click="openKCloseSettings()">
          <folder-open
            v-if="isSettingsFolderOpen"
            :style="`--element-color: #b5f0cb`"
          ></folder-open>
          <folder-close
            v-else
            :style="`--element-color: #b5f0cb`"
          ></folder-close>
          <p class="nav-title"> Clover 4 <br /> Settings</p>
        </div>
        <div class="nav-option" @click="openKCloseCaptures()">
          <folder-open
            v-if="isCapturesFolderOpen"
            :style="`--element-color: #cae8d7`"
          ></folder-open>
          <folder-close
            v-else
            :style="`--element-color: #cae8d7`"
          ></folder-close>
          <p class="nav-title"> Clover 4 <br /> Captures</p>
        </div>
        <div class="nav-option" @click="openKClosePi()">
          <folder-open
            v-if="isPiFolderOpen"
            :style="`--element-color: #cas4d7`"
          ></folder-open>
          <folder-close
            v-else
            :style="`--element-color: #cas4d7`"
          ></folder-close>
          <p class="nav-title"> Clover 4 <br /> Pi</p>
        </div>
      </div>
    </div>
    <DroneModal v-if="isDroneFolderOpen" />
    <LogsModal v-if="isLogsFolderOpen" />
    <DroneSettingsModal v-if="isSettingsFolderOpen" />
    <DroneCapturesModal v-if="isCapturesFolderOpen" />
    <DronePiModal v-if="isPiFolderOpen" />
  </div>
</template>

<script src="../scripts/IndexScreen.js"></script>
<style scoped src="../styles/IndexScreen.scss" lang="scss"></style>
