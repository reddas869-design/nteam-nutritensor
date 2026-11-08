import { lazy, Suspense, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpRight,
  Cpu,
  Fingerprint,
  Leaf,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { Button, PageHeading } from "../components/Primitives";

const ThreeScene = lazy(() => import("../components/ThreeScene"));

export default function AboutPage() {
  const [showScene, setShowScene] = useState(false);
  const { setPage } = useWorkspace();
  return (
    <main className="workspace-page about-page">
      <div className="optional-scene">
        {showScene ? (
          <Suspense fallback={<p>Loading illustration…</p>}>
            <ThreeScene />
          </Suspense>
        ) : (
          <Button variant="ghost" onClick={() => setShowScene(true)}>
            Show 3D food illustration
          </Button>
        )}
      </div>
      <PageHeading
        eyebrow="NTEAM / NUTRITENSOR"
        title="Food, with a little more context."
        text="An experimental local science day's model from ssphs that connects food understanding, mathamatice optimization and inference engineering."
      />
      <section className="about-feature">
        <div>
          <p className="eyebrow">START WITH THE PLATE</p>
          <h2>
            A clean view.
            <br />
            <em>A careful process.</em>
          </h2>
          <p>
            The camera is the starting point. Food candidates are checked
            against a catalog, portions are confirmed, and the numbers are
            calculated from source values. A large language model adds an
            explanation.
          </p>
          <Button onClick={() => setPage("capture")}>
            Explore a meal
            <ArrowUpRight size={16} />
          </Button>
        </div>
        <div className="about-process">
          {[
            {
              icon: ScanLine,
              title: "Observe",
              text: "A photo, a description, or a selected food.",
            },
            {
              icon: Fingerprint,
              title: "Ground",
              text: "Match the food and preparation to source records.",
            },
            {
              icon: Leaf,
              title: "Calculate",
              text: "Scale each record by the confirmed portion.",
            },
            {
              icon: ShieldCheck,
              title: "Review",
              text: "Keep assumptions and missing values visible.",
            },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title}>
              <Icon size={23} strokeWidth={1.5} />
              <span>
                <h3>{title}</h3>
                <p>{text}</p>
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="about-grid">
        <article>
          <Cpu size={25} />
          <h3>One runtime, several roles.</h3>
          <p>
            Sir, The GPU has a bounded queue
            and generation budget.
          </p>
        </article>
        <article>
          <ShieldCheck size={25} />
          <h3>Evidence you can inspect.</h3>
          <p>
            A photo cannot guarantee.
            model are build by a nteam, so it can make mistakes.
          </p>
        </article>
        <article>
          <Leaf size={25} />
          <h3>A workspace for curiosity.</h3>
          <p>
            This engineered project provides general food information and does not prescribe
            medical diets.
          </p>
        </article>
      </section>
      <section className="project-download">
        <div>
          <p className="eyebrow">BUILT TO BE OPENED UP</p>
          <h2>Make the workspace yours. but sir need a GPU to calculate</h2>
          <p>
            The complete source files includes harder mechanism inside a ML/LLM and deeper emphasize the cores.
          </p>
        </div>
        <a
          className="button button-primary"
          href="/downloads/nteam-nutritensor.zip"
          download
        >
          <ArrowDownToLine size={17} />
          Download project. not recomanded for general purpose
        </a>
      </section>
    </main>
  );
}
