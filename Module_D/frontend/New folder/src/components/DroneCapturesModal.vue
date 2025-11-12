<template>
  <div class="modal">
    <div class="modal-header">
      <span class="modal-icon close" @click="kcloseDroneModal()"></span>
      <span class="modal-icon"></span>
      <span class="modal-icon"></span>
      <button
        class="back-arrow"
        @click="kCloseMainImage()"
        v-if="displayImgSrc !== null"
      >
        <v-icon class="icon">mdi-chevron-left</v-icon>
      </button>
      <input
        class="zoom-controller"
        type="range"
        step="0.1"
        min="1"
        max="2"
        value="1"
        v-if="displayImgSrc !== null"
        @change="updateImageZoom($event)"
        @mousemove="updateImageZoom($event)"
      />
    </div>
    <div class="modal-body">
      <DroneImage v-show="displayImgSrc === null" />
      <div class="container" v-show="displayImgSrc === null">
        <v-row>
          <v-col
            v-for="(image, index) in images"
            :key="index"
            cols="12"
            md="6"
          >
            <v-card>
              <v-img
                :src="image.src"
                :alt="image.alt"
                max-height="300px"
                class="captures"
                :class="`image${index}`"
                @click="openImage(image.src, index)"
                draggable="false"
              ></v-img>
              <v-card-title>{{ image.alt }}</v-card-title>
            </v-card>
          </v-col>
        </v-row>
      </div>
      <MainImage
        v-if="displayImgSrc !== null"
        :displayImgSrc="displayImgSrc"
        ref="mainImage"
      ></MainImage>
    </div>
  </div>
</template>
  
<script src="../scripts/DroneCapturesModal.js"></script>
<style scoped src="../styles/Modal.scss" lang="scss"></style>
<style scoped>
    .captures {
        width: 100%;
        object-fit: contain;
        cursor: pointer;
    }
</style>
  