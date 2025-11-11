import server, {HTTP_METHODS} from "./server";
import {IAccount, IMedia, IMediaPart, IPost} from "../types/entities";

/* Media Part */
export const deleteMediaPart = async (mediaPartId: number): Promise<void> => {
    return await server.post("media_part/" + mediaPartId, {}, HTTP_METHODS.delete);
}

export const saveMediaPart = async (mediaPart: IMediaPart): Promise<void> => {
    return await server.post("media_part/", mediaPart);
}

/* Media */
export const saveMediaAnnotations = async (media: IMedia): Promise<void> => {
    return await server.post(`annotate/media/${media.id}`, {
        notes: media.notes,
        tags: media.tags?.map(t => t.id),
    });
}

/* Post */
export const savePostAnnotations = async (post: IPost): Promise<void> => {
    return await server.post(`annotate/post/${post.id}`, {
        notes: post.notes,
        tags: post.tags?.map(t => t.id),
    });
}

/* Account */
export const saveAccountAnnotations = async (account: IAccount): Promise<void> => {
    return await server.post(`annotate/account/${account.id}`, {
        notes: account.notes,
        tags: account.tags?.map(t => t.id),
    });
}