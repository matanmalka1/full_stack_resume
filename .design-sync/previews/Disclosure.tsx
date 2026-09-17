import { Disclosure } from "cv-application-frontend";

export const Default = () => (
  <div className="flex flex-col gap-4 p-4 max-w-lg">
    <Disclosure summary="הצג דרישות המשרה">
      <p className="leading-6">
        אנו מחפשים מפתח Frontend בעל ניסיון של לפחות 3 שנים ב-React. הידע ב-TypeScript הוא יתרון.
        העמדה כוללת עבודה בצוות מוצר של 8 אנשים.
      </p>
    </Disclosure>
    <Disclosure summary="פרטים טכניים נוספים">
      <p className="leading-6">
        המשרה דורשת ידע ב-REST APIs ו-GraphQL. ניסיון עם Next.js יתרון משמעותי.
        סביבת עבודה עם CI/CD מלא.
      </p>
    </Disclosure>
  </div>
);
