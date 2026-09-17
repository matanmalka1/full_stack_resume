import { Select } from "cv-application-frontend";

export const Default = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Select defaultValue="">
      <option value="" disabled>בחר רמת ניסיון</option>
      <option value="junior">Junior (0–2)</option>
      <option value="mid">Mid (2–5)</option>
      <option value="senior">Senior (5+)</option>
    </Select>
  </div>
);

export const WithValue = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Select value="senior" onChange={() => {}}>
      <option value="junior">Junior</option>
      <option value="mid">Mid</option>
      <option value="senior">Senior</option>
    </Select>
    <Select disabled value="mid" onChange={() => {}}>
      <option value="junior">Junior</option>
      <option value="mid">Mid</option>
      <option value="senior">Senior</option>
    </Select>
  </div>
);
