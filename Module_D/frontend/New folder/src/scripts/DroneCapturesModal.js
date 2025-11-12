const DroneImage = () => import("../components/DroneImage.vue");
import { droneCapturesConfig } from "./droneCapturesConfig";
import MainImage from "../components/MainImage";

export default {
    components: {
        DroneImage,
        MainImage
    },
    data() {
        return {
            images: droneCapturesConfig,
            displayImgSrc: null,
            scrollTopPosition: 0,
            imgCount: 0,
            openedImageIndex: null,
        }
    },
    methods: {
        kcloseDroneModal: function () {
            this.$parent.$data.isCapturesFolderOpen = false;
        },
        openImage: function (src, index) {
            this.displayImgSrc = src;
            this.openedImageIndex = index;
        },
        updateImageZoom: function (e) {
            this.$refs.mainImage.setImageZoom(e.target.value);
        },
        kCloseMainImage: function () {
            if (this.displayImgSrc) {
                this.$refs.mainImage.closeImage();
            }
            setTimeout(() => {
                const image = document.querySelector(`.image${this.openedImageIndex}`);
                if (image) image.scrollIntoView();
                this.openedImageIndex = null;
            }, 0);
        },
    },
};