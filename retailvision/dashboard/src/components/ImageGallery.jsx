import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ZoomIn, ChevronLeft, ChevronRight } from "lucide-react";

const GALLERY_IMAGES = [
  {
    src: "/data/viz/composite_summary.png",
    title: "Composite Summary",
    description:
      "Combined visualization showing zones, tracks, and density analysis",
  },
  {
    src: "/data/viz/detection_heatmap.png",
    title: "Detection Heatmap",
    description:
      "Spatial density of person detections across the camera field of view",
  },
  {
    src: "/data/viz/heatmap_overlay.png",
    title: "Heatmap Overlay",
    description:
      "Detection heatmap overlaid on the camera reference frame",
  },
  {
    src: "/data/viz/zones_perspective_labeled.png",
    title: "Zone Labels",
    description:
      "All discovered zones with labeled boundaries on the reference frame",
  },
];

/**
 * Image gallery displaying pipeline-generated visualization PNGs.
 * Features thumbnails grid with lightbox on click.
 */
export default function ImageGallery() {
  const [lightbox, setLightbox] = useState(null); // index of open image
  const [loadedImages, setLoadedImages] = useState({});
  const [failedImages, setFailedImages] = useState({});

  const handleImageLoad = useCallback((idx) => {
    setLoadedImages((prev) => ({ ...prev, [idx]: true }));
  }, []);

  const handleImageError = useCallback((idx) => {
    setFailedImages((prev) => ({ ...prev, [idx]: true }));
  }, []);

  const openLightbox = useCallback((idx) => {
    setLightbox(idx);
  }, []);

  const closeLightbox = useCallback(() => {
    setLightbox(null);
  }, []);

  const goNext = useCallback(() => {
    setLightbox((prev) => {
      if (prev === null) return null;
      const validImages = GALLERY_IMAGES.filter((_, i) => !failedImages[i]);
      const currentValidIdx = validImages.findIndex(
        (_, vi) =>
          GALLERY_IMAGES.indexOf(validImages[vi]) === prev
      );
      if (currentValidIdx < validImages.length - 1) {
        return GALLERY_IMAGES.indexOf(validImages[currentValidIdx + 1]);
      }
      return prev;
    });
  }, [failedImages]);

  const goPrev = useCallback(() => {
    setLightbox((prev) => {
      if (prev === null) return null;
      const validImages = GALLERY_IMAGES.filter((_, i) => !failedImages[i]);
      const currentValidIdx = validImages.findIndex(
        (_, vi) =>
          GALLERY_IMAGES.indexOf(validImages[vi]) === prev
      );
      if (currentValidIdx > 0) {
        return GALLERY_IMAGES.indexOf(validImages[currentValidIdx - 1]);
      }
      return prev;
    });
  }, [failedImages]);

  // Keyboard navigation
  useEffect(() => {
    if (lightbox === null) return;
    function handleKey(e) {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [lightbox, closeLightbox, goNext, goPrev]);

  const availableImages = GALLERY_IMAGES.filter(
    (_, i) => !failedImages[i]
  );

  if (availableImages.length === 0 && Object.keys(failedImages).length === GALLERY_IMAGES.length) {
    return null; // All images failed to load, hide the component
  }

  return (
    <>
      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Pipeline Visualizations
          </h3>
          <span className="text-[10px] font-mono text-text-secondary">
            {availableImages.length} images
          </span>
        </div>

        <div className="p-3 grid grid-cols-2 md:grid-cols-4 gap-3">
          {GALLERY_IMAGES.map((img, idx) => {
            if (failedImages[idx]) return null;
            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.08 }}
                className="group relative rounded-lg overflow-hidden bg-bg-primary border border-border cursor-pointer hover:border-accent-cyan/40 transition-colors"
                onClick={() => openLightbox(idx)}
              >
                <div className="aspect-video relative overflow-hidden">
                  <img
                    src={img.src}
                    alt={img.title}
                    className={`w-full h-full object-cover transition-all duration-300 group-hover:scale-105 ${
                      loadedImages[idx]
                        ? "opacity-100"
                        : "opacity-0"
                    }`}
                    onLoad={() => handleImageLoad(idx)}
                    onError={() => handleImageError(idx)}
                    loading="lazy"
                  />
                  {!loadedImages[idx] && !failedImages[idx] && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}

                  {/* Hover overlay */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                    <ZoomIn className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>

                <div className="px-2 py-1.5">
                  <p className="text-[11px] font-semibold text-text-primary truncate">
                    {img.title}
                  </p>
                  <p className="text-[9px] text-text-secondary truncate">
                    {img.description}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox !== null && GALLERY_IMAGES[lightbox] && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-sm flex items-center justify-center"
            onClick={closeLightbox}
          >
            {/* Close button */}
            <button
              onClick={closeLightbox}
              className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors z-10"
            >
              <X className="w-5 h-5 text-white" />
            </button>

            {/* Nav buttons */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                goPrev();
              }}
              className="absolute left-4 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors z-10"
            >
              <ChevronLeft className="w-6 h-6 text-white" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                goNext();
              }}
              className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors z-10"
            >
              <ChevronRight className="w-6 h-6 text-white" />
            </button>

            {/* Image */}
            <motion.div
              key={lightbox}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="max-w-[90vw] max-h-[85vh] flex flex-col items-center"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                src={GALLERY_IMAGES[lightbox].src}
                alt={GALLERY_IMAGES[lightbox].title}
                className="max-w-full max-h-[78vh] object-contain rounded-lg shadow-2xl"
              />
              <div className="mt-3 text-center">
                <h3 className="text-white text-sm font-semibold">
                  {GALLERY_IMAGES[lightbox].title}
                </h3>
                <p className="text-white/60 text-xs mt-0.5">
                  {GALLERY_IMAGES[lightbox].description}
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
