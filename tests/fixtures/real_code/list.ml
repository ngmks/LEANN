(**************************************************************************)
(*                                                                        *)
(*                                 OCaml                                  *)
(*                                                                        *)
(*             Xavier Leroy, projet Cristal, INRIA Rocquencourt           *)
(*                                                                        *)
(*   Copyright 1996 Institut National de Recherche en Informatique et     *)
(*     en Automatique.                                                    *)
(*                                                                        *)
(*   All rights reserved.  This file is distributed under the terms of    *)
(*   the GNU Lesser General Public License version 2.1, with the          *)
(*   special exception on linking described in the file LICENSE.          *)
(*                                                                        *)
(**************************************************************************)

(* An alias for the type of lists. *)
type 'a t = 'a list = [] | (::) of 'a * 'a list

(* List operations *)

let rec length_aux len = function
    [] -> len
  | _::l -> length_aux (len + 1) l

let length l = length_aux 0 l

let cons a l = a::l

let singleton a = [a]

let hd = function
    [] -> failwith "hd"
  | a::_ -> a

let tl = function
    [] -> failwith "tl"
  | _::l -> l

let nth l n =
  if n < 0 then invalid_arg "List.nth" else
  let rec nth_aux l n =
    match l with
    | [] -> failwith "nth"
    | a::l -> if n = 0 then a else nth_aux l (n-1)
  in nth_aux l n

let nth_opt l n =
  if n < 0 then invalid_arg "List.nth" else
  let rec nth_aux l n =
    match l with
    | [] -> None
    | a::l -> if n = 0 then Some a else nth_aux l (n-1)
  in nth_aux l n

let append = (@)

let rec rev_append l1 l2 =
  match l1 with
    [] -> l2
  | a :: l -> rev_append l (a :: l2)

let rev l = rev_append l []

let[@tail_mod_cons] rec init i last f =
  if i > last then []
  else if i = last then [f i]
  else
    let r1 = f i in
    let r2 = f (i+1) in
    r1 :: r2 :: init (i+2) last f

let init len f =
  if len < 0 then invalid_arg "List.init" else
  init 0 (len - 1) f

let rec flatten = function
    [] -> []
  | l::r -> l @ flatten r

let concat = flatten

let[@tail_mod_cons] rec map f = function
    [] -> []
  | [a1] ->
      let r1 = f a1 in
      [r1]
  | a1::a2::l ->
      let r1 = f a1 in
      let r2 = f a2 in
      r1::r2::map f l

let[@tail_mod_cons] rec mapi i f = function
    [] -> []
  | [a1] ->
      let r1 = f i a1 in
      [r1]
  | a1::a2::l ->
      let r1 = f i a1 in
      let r2 = f (i+1) a2 in
      r1::r2::mapi (i+2) f l

let mapi f l = mapi 0 f l

let rev_map f l =
  let rec rmap_f accu = function
    | [] -> accu
    | a::l -> rmap_f (f a :: accu) l
  in
  rmap_f [] l


let rec iter f = function
    [] -> ()
  | a::l -> f a; iter f l

let rec iteri i f = function
    [] -> ()
  | a::l -> f i a; iteri (i + 1) f l

let iteri f l = iteri 0 f l

let rec fold_left f accu l =
  match l with
    [] -> accu
  | a::l -> fold_left f (f accu a) l

let rec fold_right f l accu =
  match l with
    [] -> accu
  | a::l -> f a (fold_right f l accu)

let[@tail_mod_cons] rec map2 f l1 l2 =
  match (l1, l2) with
    ([], []) -> []
  | ([a1], [b1]) ->
      let r1 = f a1 b1 in
      [r1]
  | (a1::a2::l1, b1::b2::l2) ->
      let r1 = f a1 b1 in
      let r2 = f a2 b2 in
      r1::r2::map2 f l1 l2
  | (_, _) -> invalid_arg "List.map2"

let rev_map2 f l1 l2 =
  let rec rmap2_f accu l1 l2 =
    match (l1, l2) with
    | ([], []) -> accu
    | (a1::l1, a2::l2) -> rmap2_f (f a1 a2 :: accu) l1 l2
    | (_, _) -> invalid_arg "List.rev_map2"
  in
  rmap2_f [] l1 l2


let rec iter2 f l1 l2 =
  match (l1, l2) with
    ([], []) -> ()
  | (a1::l1, a2::l2) -> f a1 a2; iter2 f l1 l2
  | (_, _) -> invalid_arg "List.iter2"

let rec fold_left2 f accu l1 l2 =
  match (l1, l2) with
    ([], []) -> accu
  | (a1::l1, a2::l2) -> fold_left2 f (f accu a1 a2) l1 l2
  | (_, _) -> invalid_arg "List.fold_left2"

let rec fold_right2 f l1 l2 accu =
  match (l1, l2) with
    ([], []) -> accu
  | (a1::l1, a2::l2) -> f a1 a2 (fold_right2 f l1 l2 accu)
  | (_, _) -> invalid_arg "List.fold_right2"

let rec for_all p = function
    [] -> true
  | a::l -> p a && for_all p l

let rec exists p = function
    [] -> false
  | a::l -> p a || exists p l

let rec for_all2 p l1 l2 =
  match (l1, l2) with
    ([], []) -> true
  | (a1::l1, a2::l2) -> p a1 a2 && for_all2 p l1 l2
  | (_, _) -> invalid_arg "List.for_all2"

let rec exists2 p l1 l2 =
  match (l1, l2) with
    ([], []) -> false
  | (a1::l1, a2::l2) -> p a1 a2 || exists2 p l1 l2
  | (_, _) -> invalid_arg "List.exists2"

let rec mem x = function
    [] -> false
  | a::l -> compare a x = 0 || mem x l

let rec memq x = function
    [] -> false
  | a::l -> a == x || memq x l

let rec assoc x = function
