import { IdeaValidatorPanel } from "@/components/IdeaValidatorPanel";

export default function Home() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Paraguay Startup Validator
          </h1>
          <p className="text-gray-500 text-sm">
            Validá tu idea contra datos reales del DNIT, MIC y prensa paraguaya
          </p>
        </div>
        <IdeaValidatorPanel />
      </div>
    </main>
  );
}
