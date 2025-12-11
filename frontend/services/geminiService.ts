import { GoogleGenAI } from "@google/genai";

// Initialize Gemini Client
// NOTE: In a production environment, API keys should be handled via backend proxy or strictly controlled environment variables.
const apiKey = process.env.API_KEY || ''; 
const ai = new GoogleGenAI({ apiKey });

/**
 * Uses Gemini 2.5 Flash to generate a smart summary and Arabic metadata 
 * for the video based on the provided URL (simulated extraction).
 */
export const generateVideoInsights = async (videoUrl: string): Promise<{ title: string; summary: string }> => {
  if (!apiKey) {
    console.warn("API Key missing for Gemini Service");
    return {
      title: "فيديو تجريبي",
      summary: "لم يتم تكوين مفتاح API الخاص بـ Gemini. هذا ملخص تلقائي."
    };
  }

  try {
    // We are simulating that we extracted the description/transcript from the video URL.
    // In a real flow, the backend extracts the text, and we pass it here.
    // For this frontend demo, we ask Gemini to hallucinate a plausible summary based on the "intent".
    
    const model = 'gemini-2.5-flash';
    const prompt = `
      You are an AI assistant for a Dubbing Platform called "Arab Dubbing" (دبلجة العرب).
      The user provided this YouTube URL: ${videoUrl}.
      
      Since I cannot browse the live web, please generate a REALISTIC but FICTIONAL metadata response 
      as if you analyzed a popular educational tech video.
      
      Output ONLY a JSON object with this structure:
      {
        "arabicTitle": "A catchy title in Arabic",
        "arabicSummary": "A concise 2-sentence summary in Arabic explaining what the video is about."
      }
    `;

    const response = await ai.models.generateContent({
      model: model,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
      }
    });

    const text = response.text;
    if (!text) throw new Error("No response from Gemini");

    const parsed = JSON.parse(text);
    return {
      title: parsed.arabicTitle || "فيديو يوتيوب",
      summary: parsed.arabicSummary || "لا يوجد ملخص متاح."
    };

  } catch (error) {
    console.error("Gemini Insight Error:", error);
    return {
      title: "معالجة الفيديو",
      summary: "جاري تحليل محتوى الفيديو..."
    };
  }
};