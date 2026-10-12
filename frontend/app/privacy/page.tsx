import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy and terms" };

const REPO = "https://github.com/GAWI01/fantasy-football-ai";
const CONTACT = `${REPO}/issues`;

/** Privacy notice, terms of use and the contact/takedown route. Keep in step with what the code does. */
export default function PrivacyPage() {
  return (
    <div className="stack legal-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Last updated 11 October 2026</span>
          <h1>Privacy and terms</h1>
          <p className="page-lede">What Fantasy Football AI does with data, in plain words.</p>
        </div>
      </header>

      <section className="card">
        <h2>Who runs this</h2>
        <p>
          Fantasy Football AI is a free, independent, non-commercial tool made by{" "}
          <a href="https://github.com/GAWI01">GAWI01</a>. It is not affiliated with or endorsed by the Premier League,
          Fantasy Premier League or any football club, and it never logs in to FPL or changes your team. Questions, privacy requests and
          takedown requests: <a href={CONTACT}>open an issue on GitHub</a>.
        </p>
      </section>

      <section className="card">
        <h2>What data is used</h2>
        <ul>
          <li><b>Your Team ID.</b> You enter it. The app uses it to request your team&rsquo;s public data from the official FPL API (team name, picks, history, transfers, leagues) and to calculate your plan. It is not stored on our servers.</li>
          <li><b>Mini-leagues.</b> The league page shows the team names, scores and public squads of the managers in your private leagues, read from FPL&rsquo;s public standings when you open it. Managers&rsquo; personal names are not shown, and nothing is stored.</li>
          <li><b>Player and fixture data</b> come from the public FPL API. Historical seasons come from{" "}
            <a href="https://github.com/vaastav/Fantasy-Premier-League">vaastav/Fantasy-Premier-League</a> by Vaastav Anand, used with his permission.</li>
        </ul>
        <p>FPL responses are cached in server memory for a few minutes to limit the load on FPL. There is no database of users or teams.</p>
      </section>

      <section className="card">
        <h2>Your browser</h2>
        <p>There are no cookies, no analytics and no trackers. Fonts are served by this site, not by Google. The app keeps these settings in your browser&rsquo;s local storage, on your device only:</p>
        <ul>
          <li><code>fpl-ai-team-id</code>: the Team ID you connected</li>
          <li><code>fpl-ai-free-transfers</code>: free transfers you set yourself</li>
          <li><code>fpl-ai-plan-history</code>: earlier plans, to show when the advice changes</li>
          <li><code>fpl-ai-season-goal</code>, <code>fpl-ai-season-goal-change</code>: your season goal</li>
          <li><code>fpl-ai-motion</code>: how much the app moves (Settings → Motion)</li>
          <li><code>fpl-ai-overview-sections</code>: which Overview sections you opened or closed</li>
        </ul>
        <p><b>Disconnect team</b> in Settings deletes all of them. So does clearing this site&rsquo;s data in your browser.</p>
      </section>

      <section className="card">
        <h2>Servers and logs</h2>
        <p>
          The website is hosted by Vercel and the API by Railway. Like any web host, their infrastructure processes
          your IP address to deliver pages and protect the service, and keeps short-lived logs under their own retention
          policies. The app&rsquo;s own logs record the route (with Team and league IDs removed), the status and the
          response time, never your Team ID. Each IP address is limited to a fair number of requests per minute so one
          visitor cannot exhaust the shared budget of requests to FPL.
        </p>
        <p>
          The legal basis is a legitimate interest in providing the tool you ask for (GDPR Art. 6(1)(f)). You can ask
          what is processed about you, or object, through the contact above. Because nothing is stored, there is
          usually nothing to delete beyond your own browser storage.
        </p>
      </section>

      <section className="card">
        <h2>Terms of use</h2>
        <ul>
          <li>Recommendations are model forecasts and opinions, not guarantees. Decide yourself and make changes in the official FPL app.</li>
          <li>The service is provided free, as is, without warranty, and may change or stop at any time.</li>
          <li>Do not use it to scrape or bulk-download data, or to overload the service.</li>
          <li>FPL and Premier League data, names and marks belong to their owners. Club colours are shown on simplified kits drawn for this site; they are not official designs or replicas.</li>
        </ul>
        <p>
          <b>Rights holders:</b> if you believe something here infringes your rights, <a href={CONTACT}>open an issue</a>{" "}
          describing it and it will be reviewed and, where justified, removed promptly.
        </p>
      </section>
    </div>
  );
}
