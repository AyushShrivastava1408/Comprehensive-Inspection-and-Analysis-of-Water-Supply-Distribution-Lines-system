// Example React component: Upload -> Analyze -> Annotated results. Apne UI ke hisaab se style karo.
import { useState } from "react";
import { uploadImages, analyze, waitForAnalysis, getImages, getDetections, imageUrl, downloadPdf } from "./api";

export default function UploadAnalyze() {
  const [files, setFiles] = useState([]);
  const [msg, setMsg] = useState("");
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null); // {inspection, images, detections}

  async function run() {
    try {
      setMsg("Uploading..."); setResult(null);
      const up = await uploadImages(files, { title: "Field inspection" });
      if (up.rejected.length) setMsg("Skipped: " + up.rejected.map((r) => `${r.filename} (${r.reason})`).join("; "));
      const id = up.inspection.id;
      await analyze(id);
      const done = await waitForAnalysis(id, { onProgress: (i) => setProgress(`${i.images_processed}/${i.image_count}`) });
      if (done.status === "failed") return setMsg("Analysis failed: " + done.error);
      const [images, dets] = await Promise.all([getImages(id), getDetections(id)]);
      setResult({ inspection: done, images: images.items, detections: dets.items });
      setMsg(done.status === "partial" ? "Some images failed (see list)" : "Done");
    } catch (e) {
      setMsg(e.status === 400 && e.details ? e.details.map((d) => `${d.filename}: ${d.reason}`).join("; ") : e.message);
    }
  }

  return (
    <div>
      <input type="file" accept=".jpg,.jpeg,.png" multiple onChange={(e) => setFiles([...e.target.files])} />
      <button disabled={!files.length} onClick={run}>Upload & Analyze</button>
      <p>{msg} {progress && `(${progress})`}</p>
      {result?.images.map((img) => (
        <div key={img.id}>
          <h4>{img.original_filename} - {img.detection_count} detection(s) {img.quality_warnings.join(", ")}</h4>
          <img src={imageUrl(img.annotated_url || img.original_url, 800)} alt="" style={{ maxWidth: 400 }} />
          <ul>
            {result.detections.filter((d) => d.image_id === img.id).map((d) => (
              <li key={d.id}>{d.defect_type} - {(d.confidence * 100).toFixed(1)}% ({d.severity_level})</li>
            ))}
          </ul>
        </div>
      ))}
      {result && <button onClick={() => downloadPdf(result.inspection.id)}>Download PDF report</button>}
    </div>
  );
}
