import React from "react";

type IEntityDisplayOption = "display" | "hide" | "collapse";
type IEntityAnnotatorOption = "show" | "hide" | "disable";
type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

interface IEntityViewerConfig {
    all: {
        hideInnerLinks?: boolean;
    }
    account: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        postsPageSize?: number | null;
    }
    post: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        compactMode?: boolean;
    }
    media: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    mediaPart: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
        style?: React.CSSProperties;
    }
    archivingSession: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    comment: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    postLike: {
        display: IEntityDisplayOption;
        annotator: IEntityAnnotatorOption;
    }
    taggedAccount: {
        display: IEntityDisplayOption;
    }
    accountRelation: {
        display: IEntityDisplayOption;
    }
}

export class EntityViewerConfig implements IEntityViewerConfig {
    all = {
        hideInnerLinks: false
    }
    account = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        postsPageSize: null
    };
    post = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        compactMode: false,
    };
    media = {
        display: "display" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    mediaPart = {
        display: "hide" as IEntityDisplayOption,
        annotator: "show" as IEntityAnnotatorOption,
        style: {} as React.CSSProperties,
    };
    archivingSession = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    comment = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    postLike = {
        display: "hide" as IEntityDisplayOption,
        annotator: "hide" as IEntityAnnotatorOption,
    };
    taggedAccount = {
        display: "display" as IEntityDisplayOption,
    };
    accountRelation = {
        display: "display" as IEntityDisplayOption,
    };

    constructor(config?: DeepPartial<IEntityViewerConfig>) {
        if (!config) return;
        const merge = (target: object, source: object | undefined) => {
            if (source) Object.assign(target, source);
        };
        merge(this.all, config.all);
        merge(this.account, config.account);
        merge(this.post, config.post);
        merge(this.media, config.media);
        merge(this.mediaPart, config.mediaPart);
        merge(this.archivingSession, config.archivingSession);
        merge(this.comment, config.comment);
        merge(this.postLike, config.postLike);
        merge(this.taggedAccount, config.taggedAccount);
        merge(this.accountRelation, config.accountRelation);
    }
}
