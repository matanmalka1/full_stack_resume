import { PageHeading } from "cv-application-frontend";

export const Default = () => (
  <div className="p-6 max-w-2xl">
    <PageHeading id="heading-default">ניתוח הגשה</PageHeading>
  </div>
);

export const WithEyebrow = () => (
  <div className="p-6 max-w-2xl">
    <PageHeading id="heading-eyebrow" eyebrow="Frontend Engineer · Google">
      סקירת קורות חיים
    </PageHeading>
  </div>
);

export const WithDescription = () => (
  <div className="p-6 max-w-2xl">
    <PageHeading
      id="heading-desc"
      eyebrow="שלב 2 מתוך 4"
      eyebrowTone="accent"
      description="עיין בניתוח ובחר את הכישורים הרלוונטיים להגשה זו"
    >
      בחירת כישורים
    </PageHeading>
  </div>
);
