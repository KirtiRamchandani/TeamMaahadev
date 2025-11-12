<template>
    <div class="modal">
      <div class="modal-header">
        <span class="modal-icon close" @click="kcloseDroneModal()"></span>
        <span class="modal-icon"></span>
        <span class="modal-icon"></span>
      </div>
      <div class="modal-body">
        <DroneImage />
        <v-expansion-panels multiple>
          <v-expansion-panel>
            <v-expansion-panel-header>Drone Details</v-expansion-panel-header>
            <v-expansion-panel-content>
              <v-data-table
                :headers="headers"
                :items="droneDetails"
                class="elevation-1"
                hide-default-footer
              >
                <template v-slot:item.value="{ item }">
                  <span v-if="isLink(item.value)">
                    <a :href="item.value" target="_blank">{{ item.value }}</a>
                  </span>
                  <span v-else>{{ item.value }}</span>
                </template>
              </v-data-table>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
        <v-expansion-panels multiple>
          <v-expansion-panel>
            <v-expansion-panel-header>Drone Controller</v-expansion-panel-header>
            <v-expansion-panel-content>
              <div class="btn-container">
                <v-btn @click="turnOnDrone" :disabled="droneOn">
                  Turn On Drone
                </v-btn>
                <v-btn @click="turnOffDrone" :disabled="!droneOn" class="turn-off-btn">
                  Turn Off Drone
                </v-btn>
              </div>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>
    </div>
  </template>
  
  <script src="../scripts/DroneSettingsModal.js"></script>
  <style scoped src="../styles/Modal.scss" lang="scss"></style>
  <style scoped src="../styles/DroneSettingsModal.scss" lang="scss"></style>
  